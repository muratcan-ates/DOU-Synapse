"""Yerel embedding RSS ölçümü; servis/DB veya model kalitesi kabulü değildir.

Yeni süreçte ilk ve ikinci sorgu, gerçek process_document hattı ve aynı anda API
lifespan + worker belge işleme bileşenleri ölçülür. Model indirilmez. Her RSS satırı
tek ps gözlemidir; toplam tepe ayrı süreç tepelerinin toplamı değildir. Örnekleme
kısa tepeleri kaçırabilir, paylaşılan sayfaları iki kez sayabilir. İşletim sistemi
dosya önbelleği temizlenmez. Hashing yalnız ölçücü mekanizmasının kontrolüdür.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import selectors
import socket
import subprocess
import sys
import tempfile
import time
from itertools import pairwise
from pathlib import Path
from typing import Any
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
MODEL = "intfloat/multilingual-e5-large"
QINT8_SHA = "46f5d13dba7ade0160c67d346087d870162950882be17ff9319f873cf6fedff1"
QINT8_UPSTREAM = (
    "https://huggingface.co/intfloat/multilingual-e5-large/"
    "blob/3d7cfbdacd47fdda877c5cd8a79fbcc4f2a574f3/onnx/model_qint8_avx512_vnni.onnx"
)
QUERY = "İşletim sistemi sanal belleği nasıl yönetir?"
MIB = 1024 * 1024

# Çocuk protokolü serbest hata metni taşımaz; yalnız önceden tanımlanmış değerler.
CHILD_ERROR_CODES = frozenset(
    {
        "CHILD_OPERATION_FAILED",
        "NETWORK_FORBIDDEN",
        "NETWORK_ATTEMPT_OBSERVED",
        "PARENT_COMMAND_INVALID",
        "ARTIFACT_TOO_LARGE",
        "ARTIFACT_CHANGED_DURING_HASH",
        "VECTOR_DIMENSION_INVALID",
        "VECTOR_NONFINITE",
        "VECTOR_ZERO",
        "SYNTHETIC_STORAGE_KEY_INVALID",
        "INGEST_CHUNKS_MISSING",
        "API_WARMUP_FAILED",
        "QINT8_PAD_TOKEN_MISSING",
        "QINT8_OUTPUT_MISSING",
        "QINT8_OUTPUT_NONFINITE",
        "QINT8_OUTPUT_SHAPE_INVALID",
    }
)
_EXCEPTION_CATEGORIES = {
    ("builtins", name): category
    for name, category in {
        "MemoryError": "MEMORY_ERROR",
        "PermissionError": "PERMISSION_ERROR",
        "FileNotFoundError": "FILE_NOT_FOUND",
        "OSError": "OS_ERROR",
        "ImportError": "IMPORT_ERROR",
        "ModuleNotFoundError": "MODULE_NOT_FOUND",
        "TimeoutError": "TIMEOUT_ERROR",
        "RuntimeError": "RUNTIME_ERROR",
        "ValueError": "VALUE_ERROR",
        "TypeError": "TYPE_ERROR",
        "KeyError": "KEY_ERROR",
        "AssertionError": "ASSERTION_ERROR",
        "KeyboardInterrupt": "INTERRUPTED",
        "SystemExit": "SYSTEM_EXIT",
    }.items()
}
_EXCEPTION_CATEGORIES.update(
    {
        ("onnxruntime.capi.onnxruntime_pybind11_state", name): category
        for name, category in {
            "Fail": "ONNX_FAIL",
            "InvalidArgument": "ONNX_INVALID_ARGUMENT",
            "NoSuchFile": "ONNX_FILE_NOT_FOUND",
            "InvalidGraph": "ONNX_INVALID_GRAPH",
            "RuntimeException": "ONNX_RUNTIME_ERROR",
            "NotImplemented": "ONNX_NOT_IMPLEMENTED",
            "EPFail": "ONNX_PROVIDER_ERROR",
        }.items()
    }
)
_EXCEPTION_CATEGORIES.update(
    {
        ("huggingface_hub.errors", "LocalEntryNotFoundError"): "CACHE_ENTRY_MISSING",
        ("huggingface_hub.errors", "OfflineModeIsEnabled"): "OFFLINE_MODE",
        ("pydantic_core._pydantic_core", "ValidationError"): "VALIDATION_ERROR",
    }
)
CHILD_EXCEPTION_CATEGORIES = frozenset(
    {*_EXCEPTION_CATEGORIES.values(), "MEASUREMENT_ERROR", "UNCLASSIFIED_ERROR"}
)


class NetworkGuard:
    """Python soket girişimlerini sayar ve reddeder; OS firewall garantisi değildir."""

    def __init__(self) -> None:
        self.attempts = 0
        self.blocked_local_ipv6_probe = 0

    @staticmethod
    def _local_ipv6_probe(values: tuple[Any, ...]) -> bool:
        """Yalnız tam IPv6 loopback/port0 stream bind şekli; işlem yine reddedilir."""
        if type(values) is not tuple or len(values) != 2:
            return False
        sock, address = values
        return (
            isinstance(sock, socket.socket)
            and sock.family == socket.AF_INET6
            and sock.type == socket.SOCK_STREAM
            and type(address) is tuple
            and 2 <= len(address) <= 4
            and type(address[0]) is str
            and address[0] == "::1"
            and all(type(value) is int and value == 0 for value in address[1:])
        )

    def audit(self, event: str, values: tuple[Any, ...]) -> None:
        if event in {
            "socket.connect",
            "socket.connect_ex",
            "socket.bind",
            "socket.getaddrinfo",
        }:
            if event == "socket.bind" and self._local_ipv6_probe(values):
                # urllib3 içe aktarımı bu engeli yakalar; bind hiçbir zaman çalışmaz.
                self.blocked_local_ipv6_probe += 1
            else:
                self.attempts += 1
            raise MeasurementError("NETWORK_FORBIDDEN")


class MeasurementError(Exception):
    """Sabit hata kodları; istisna metni ve ortam sırları rapora aktarılmaz."""


def child_failure_diagnostics(
    exc: BaseException, network: NetworkGuard, source_before: str | None
) -> dict[str, Any]:
    """Serbest hata metni/traceback okunmaz; dahili hata kodu da izin listesine bağlıdır."""
    code = "CHILD_OPERATION_FAILED"
    if isinstance(exc, MeasurementError):
        if len(exc.args) == 1 and type(exc.args[0]) is str and exc.args[0] in CHILD_ERROR_CODES:
            code = exc.args[0]
        category = "MEASUREMENT_ERROR"
    else:
        category = _EXCEPTION_CATEGORIES.get(
            (type(exc).__module__, type(exc).__name__), "UNCLASSIFIED_ERROR"
        )
    try:
        source_after = manifest_digest(source_manifest())
    except BaseException:
        # Kaynak okuma hatası özgün hatayı örtmez; elde edilemeyen özet null kalır.
        source_after = None
    return {
        "code": code,
        "exception_category": category,
        "network_attempts": network.attempts,
        "blocked_local_ipv6_probe": network.blocked_local_ipv6_probe,
        "source_digest_before": source_before,
        "source_digest_after": source_after,
    }


def validated_child_failure(event: dict[str, Any]) -> dict[str, Any]:
    """Çocuk çıktısı doğrulanmadan kanıta taşınmaz; ek alanlar bile reddedilir."""
    require(
        set(event)
        == {
            "event",
            "code",
            "exception_category",
            "network_attempts",
            "blocked_local_ipv6_probe",
            "source_digest_before",
            "source_digest_after",
        },
        "CHILD_PROTOCOL_INVALID",
    )
    require(
        type(event["code"]) is str and event["code"] in CHILD_ERROR_CODES,
        "CHILD_PROTOCOL_INVALID",
    )
    require(
        type(event["exception_category"]) is str
        and event["exception_category"] in CHILD_EXCEPTION_CATEGORIES,
        "CHILD_PROTOCOL_INVALID",
    )
    for counter in ("network_attempts", "blocked_local_ipv6_probe"):
        require(type(event[counter]) is int and event[counter] >= 0, "CHILD_PROTOCOL_INVALID")
    for key in ("source_digest_before", "source_digest_after"):
        value = event[key]
        require(
            value is None
            or (
                type(value) is str
                and len(value) == 64
                and all(c in "0123456789abcdef" for c in value)
            ),
            "CHILD_PROTOCOL_INVALID",
        )
    return {key: value for key, value in event.items() if key != "event"}


def require(condition: bool, code: str) -> None:
    if not condition:
        raise MeasurementError(code)


def file_digest(path: Path) -> dict[str, Any]:
    """Büyük model ağırlıkları belleğe tek parça alınmadan özetlenir."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        require(before.st_size <= 8 * 1024**3, "ARTIFACT_TOO_LARGE")
        while block := stream.read(MIB):
            digest.update(block)
        after = os.fstat(stream.fileno())
    require(
        (before.st_ino, before.st_size, before.st_mtime_ns)
        == (after.st_ino, after.st_size, after.st_mtime_ns),
        "ARTIFACT_CHANGED_DURING_HASH",
    )
    return {"sha256": digest.hexdigest(), "bytes": after.st_size}


def manifest_digest(manifest: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()


def source_manifest() -> dict[str, Any]:
    paths = sorted((ROOT / "apps/api/app").rglob("*.py"))
    paths.append(Path(__file__).resolve())
    return {str(path.relative_to(ROOT)): file_digest(path) for path in paths}


def model_manifest(cache: Path | None, provider: str) -> dict[str, Any]:
    if provider == "hashing":
        return {"provider": "hashing", "model_files": {}}
    require(cache is not None, "CACHE_REQUIRED")
    model_root = cache / "models--qdrant--multilingual-e5-large-onnx"
    snapshots = sorted(path for path in (model_root / "snapshots").glob("*") if path.is_dir())
    require(len(snapshots) == 1, "SINGLE_PINNED_SNAPSHOT_REQUIRED")
    snapshot = snapshots[0]
    files = [
        snapshot / name
        for name in (
            "model.onnx",
            "model.onnx_data",
            "config.json",
            "tokenizer.json",
            "tokenizer_config.json",
            "special_tokens_map.json",
        )
    ]
    for name in ("files_metadata.json", "refs/main"):
        path = model_root / name
        if path.exists():
            files.append(path)
    require(all(path.is_file() for path in files), "MODEL_FILE_MISSING")
    require(
        all(path.resolve().is_relative_to(cache.resolve()) for path in files),
        "MODEL_PATH_OUTSIDE_CACHE",
    )
    return {
        "provider": "fastembed",
        "model": MODEL,
        "snapshot": snapshot.name,
        "model_files": {str(path.relative_to(cache)): file_digest(path) for path in files},
    }


def synthetic_document(paragraphs: int) -> bytes:
    sentence = (
        "Sanal bellek süreçlerin adres alanını fiziksel bellekten ayırır. "
        "Page tables map virtual addresses to physical frames. "
        "Sayfa hatasında işletim sistemi eksik sayfayı yükler. "
    )
    return "\n\n".join(
        f"## Sentetik ders bölümü {index}\n\n{sentence * 8}" for index in range(paragraphs)
    ).encode()


def parse_rss(raw: str, expected: set[int]) -> dict[int, int]:
    """ps RSS birimi KiB'dir; eksik/tekrarlı gözlem sıfıra çevrilmez."""
    values: dict[int, int] = {}
    for line in raw.splitlines():
        fields = line.split()
        require(
            len(fields) == 2 and all(field.isdigit() for field in fields),
            "RSS_PARSE_FAILED",
        )
        pid, kib = map(int, fields)
        require(pid in expected and pid not in values and kib > 0, "RSS_INVALID_OBSERVATION")
        values[pid] = kib * 1024
    require(set(values) == expected, "RSS_PID_MISSING")
    return values


def observe(pids: set[int]) -> dict[str, Any]:
    started = time.monotonic_ns()
    try:
        result = subprocess.run(  # noqa: S603 - sabit ps yolu ve kendi PID listemiz
            ["/bin/ps", "-o", "pid=,rss=", "-p", ",".join(map(str, sorted(pids)))],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise MeasurementError("RSS_OBSERVER_FAILED") from None
    require(result.returncode == 0, "RSS_OBSERVER_FAILED")
    rss = parse_rss(result.stdout, pids)
    return {
        "started_monotonic_ns": started,
        "finished_monotonic_ns": time.monotonic_ns(),
        "rss_bytes": {str(pid): value for pid, value in rss.items()},
        "sum_rss_bytes": sum(rss.values()),
    }


def aggregate(samples: list[dict[str, Any]]) -> dict[str, Any]:
    require(bool(samples), "NO_RSS_SAMPLES")
    peak = max(samples, key=lambda item: item["sum_rss_bytes"])
    gaps = [
        (right["started_monotonic_ns"] - left["started_monotonic_ns"]) / 1_000_000
        for left, right in pairwise(samples)
    ]
    return {
        "samples": len(samples),
        "peak_sum_rss_bytes": peak["sum_rss_bytes"],
        "peak": peak,
        "max_sample_gap_ms": max(gaps) if gaps else None,
        "peak_is_sampled_lower_bound": True,
    }


def clean_environment(work: Path) -> dict[str, str]:
    """Çağıranın anahtarları, DB adresleri ve .env dosyası çocuklara geçmez."""
    return {
        "PATH": "/usr/bin:/bin:/usr/local/bin",
        "LANG": "C.UTF-8",
        "PYTHONUNBUFFERED": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": str(ROOT / "apps/api"),
        "HF_HUB_OFFLINE": "1",
        "HF_HUB_DISABLE_TELEMETRY": "1",
        "HF_HUB_DISABLE_IMPLICIT_TOKEN": "1",
        "HF_TOKEN_PATH": str(work / "no-token"),
        "HF_HOME": str(work / "hf"),
        "TMPDIR": str(work),
        "ENVIRONMENT": "local",
        "DEV_AUTH_ENABLED": "true",
        "LITELLM_LOCAL_MODEL_COST_MAP": "True",
        "DO_NOT_TRACK": "1",
    }


def stop_children(children: dict[str, subprocess.Popen[bytes]]) -> dict[str, Any]:
    """Yalnız bu ölçücünün başlattığı süreçler sonlandırılır ve beklenir."""
    results: dict[str, Any] = {}
    for role, process in children.items():
        results[role] = {
            "pid": process.pid,
            "action": "already-exited",
            "reaped": False,
        }
        if process.poll() is None:
            results[role]["action"] = "terminate"
            process.terminate()
    for role, process in children.items():
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            results[role]["action"] = "kill"
            process.kill()
            process.wait(timeout=5)
        results[role].update(
            {"returncode": process.returncode, "reaped": process.returncode is not None}
        )
        for stream in (process.stdin, process.stdout):
            if stream is not None:
                stream.close()
    return results


def send(process: subprocess.Popen[bytes], command: str) -> None:
    require(process.stdin is not None, "CHILD_STDIN_MISSING")
    try:
        process.stdin.write((command + "\n").encode())
        process.stdin.flush()
    except (BrokenPipeError, OSError):
        raise MeasurementError("CHILD_COMMAND_FAILED") from None


def measure_group(args: argparse.Namespace, roles: list[str], work: Path) -> dict[str, Any]:
    expected_source = manifest_digest(source_manifest())
    group_record: dict[str, Any] = {}
    children: dict[str, subprocess.Popen[bytes]] = {}
    buffers: dict[str, bytes] = {}
    phases: dict[str, str] = {}
    starts: dict[str, dict[str, Any]] = {}
    phase_results: list[dict[str, Any]] = []
    samples: list[dict[str, Any]] = []
    completed: set[str] = set()
    child_failures: dict[str, dict[str, Any]] = {}
    network_attempts: dict[str, int] = {}
    blocked_local_ipv6_probe: dict[str, int] = {}
    first_starts: set[str] = set()
    began = time.monotonic()
    released = False
    selector = selectors.DefaultSelector()

    def sample() -> None:
        value = observe({process.pid for process in children.values()})
        value["phases"] = dict(phases)
        samples.append(value)
        require(value["sum_rss_bytes"] <= args.rss_budget_mib * MIB, "RSS_BUDGET_EXCEEDED")

    try:
        for role in roles:
            command = [
                sys.executable,
                str(Path(__file__).resolve()),
                "--child",
                role,
                "--provider",
                args.provider,
                "--paragraphs",
                str(args.paragraphs),
            ]
            for option in ("cache_dir", "qint8_model", "qint8_tokenizer"):
                value = getattr(args, option)
                if value is not None:
                    command.extend(["--" + option.replace("_", "-"), str(value)])
            process = subprocess.Popen(  # noqa: S603 - aynı betik, kabuk kullanılmıyor
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                cwd=work,
                env=clean_environment(work),
                start_new_session=True,
            )
            children[role] = process
            require(process.stdout is not None, "CHILD_STDOUT_MISSING")
            os.set_blocking(process.stdout.fileno(), False)
            selector.register(process.stdout, selectors.EVENT_READ, role)
            buffers[role] = b""
        while len(completed) != len(roles):
            require(time.monotonic() - began < args.timeout_seconds, "MEASUREMENT_TIMEOUT")
            sample()
            events = selector.select(timeout=args.interval_ms / 1000)
            for key, _ in events:
                role = key.data
                data = os.read(key.fd, 16384)
                require(bool(data), "CHILD_EXITED_EARLY")
                buffers[role] += data
                require(len(buffers[role]) <= 32768, "CHILD_PROTOCOL_TOO_LARGE")
                while b"\n" in buffers[role]:
                    raw, buffers[role] = buffers[role].split(b"\n", 1)
                    try:
                        event = json.loads(raw)
                    except (ValueError, UnicodeError):
                        raise MeasurementError("CHILD_PROTOCOL_INVALID") from None
                    require(isinstance(event, dict), "CHILD_PROTOCOL_INVALID")
                    kind = event.get("event")
                    if kind == "phase_start":
                        require(
                            role not in phases and role not in completed,
                            "CHILD_PHASE_INVALID",
                        )
                        name = event.get("phase")
                        require(
                            name
                            in {
                                "cold_query",
                                "warm_query",
                                "ingest",
                                "api_lifecycle",
                                "qint8_smoke",
                            },
                            "CHILD_PHASE_INVALID",
                        )
                        phases[role] = name
                        sample()
                        starts[role] = {"sample_index": len(samples) - 1}
                        first_starts.add(role)
                        if released:
                            send(children[role], "continue")
                        elif first_starts == set(roles):
                            released = True
                            # İki ilk işlem, tek RSS çerçevesi alındıktan sonra serbest bırakılır.
                            sample()
                            for child in children.values():
                                send(child, "continue")
                    elif kind == "phase_done":
                        require(
                            role in phases and event.get("phase") == phases[role],
                            "CHILD_PHASE_INVALID",
                        )
                        sample()
                        phase_samples = samples[starts[role]["sample_index"] :]
                        detail = event.get("detail")
                        require(isinstance(detail, dict), "CHILD_PROTOCOL_INVALID")
                        phase_results.append(
                            {
                                "role": role,
                                "phase": phases.pop(role),
                                "rss_before_bytes": phase_samples[0]["rss_bytes"][
                                    str(children[role].pid)
                                ],
                                "rss_after_bytes": phase_samples[-1]["rss_bytes"][
                                    str(children[role].pid)
                                ],
                                "sampled_peak_rss_bytes": max(
                                    item["rss_bytes"][str(children[role].pid)]
                                    for item in phase_samples
                                ),
                                "first_sample_index": starts[role]["sample_index"],
                                "last_sample_index": len(samples) - 1,
                                "detail": detail,
                            }
                        )
                        send(children[role], "continue")
                    elif kind == "complete":
                        require(
                            role not in phases and role not in completed,
                            "CHILD_PHASE_INVALID",
                        )
                        for counter in ("network_attempts", "blocked_local_ipv6_probe"):
                            require(
                                type(event.get(counter)) is int and event[counter] >= 0,
                                "CHILD_PROTOCOL_INVALID",
                            )
                        require(event["network_attempts"] == 0, "CHILD_NETWORK_ATTEMPT")
                        require(
                            event.get("source_digest_before") == expected_source
                            and event.get("source_digest_after") == expected_source,
                            "CHILD_SOURCE_CHANGED",
                        )
                        network_attempts[role] = 0
                        blocked_local_ipv6_probe[role] = event["blocked_local_ipv6_probe"]
                        completed.add(role)
                    elif kind == "error":
                        diagnostic = validated_child_failure(event)
                        child_failures[role] = diagnostic
                        network_attempts[role] = diagnostic["network_attempts"]
                        blocked_local_ipv6_probe[role] = diagnostic["blocked_local_ipv6_probe"]
                        raise MeasurementError("CHILD_REPORTED_FAILURE")
                    else:
                        raise MeasurementError("CHILD_PROTOCOL_INVALID")
        sample()
        for process in children.values():
            send(process, "stop")
        exit_codes = {role: process.wait(timeout=5) for role, process in children.items()}
        require(all(code == 0 for code in exit_codes.values()), "CHILD_EXIT_FAILED")
        group_record.update(
            {
                "roles": roles,
                "pids": {role: child.pid for role, child in children.items()},
                "exit_codes": exit_codes,
                "phases": phase_results,
                "aggregate": aggregate(samples),
                "observations": samples,
                "source_manifest_digest": expected_source,
                "network_attempts": 0,
                "network_attempts_by_role": network_attempts,
                "blocked_local_ipv6_probe": sum(blocked_local_ipv6_probe.values()),
                "blocked_local_ipv6_probe_by_role": blocked_local_ipv6_probe,
            }
        )
        return group_record
    except Exception as exc:
        if isinstance(exc, subprocess.TimeoutExpired):
            failure = MeasurementError("CHILD_EXIT_TIMEOUT")
        else:
            failure = exc if isinstance(exc, MeasurementError) else MeasurementError("GROUP_FAILED")
        group_record.update(
            {
                "roles": roles,
                "pids": {role: child.pid for role, child in children.items()},
                "phases": phase_results,
                "active_phases": phases,
                "completed_roles": sorted(completed),
                "observations": samples,
                "child_failures": child_failures,
                "source_manifest_digest": expected_source,
                "network_attempts_by_role": {role: network_attempts.get(role) for role in roles},
                "network_attempts": (
                    sum(network_attempts.values()) if set(network_attempts) == set(roles) else None
                ),
                "blocked_local_ipv6_probe_by_role": {
                    role: blocked_local_ipv6_probe.get(role) for role in roles
                },
                "blocked_local_ipv6_probe": (
                    sum(blocked_local_ipv6_probe.values())
                    if set(blocked_local_ipv6_probe) == set(roles)
                    else None
                ),
            }
        )
        failure.measurement = group_record
        raise failure from None
    finally:
        selector.close()
        group_record["cleanup"] = stop_children(children)


def validate_vector(vector: Any) -> None:
    require(len(vector) == 1024, "VECTOR_DIMENSION_INVALID")
    require(all(math.isfinite(float(value)) for value in vector), "VECTOR_NONFINITE")
    require(sum(float(value) ** 2 for value in vector) > 0, "VECTOR_ZERO")


async def prepare_document(paragraphs: int) -> dict[str, Any]:
    from app.modules.ingestion.claims import Claim
    from app.modules.ingestion.pipeline import process_document

    content = synthetic_document(paragraphs)

    class MemoryStorage:
        async def load(self, key: str) -> bytes:
            require(key == "synthetic.md", "SYNTHETIC_STORAGE_KEY_INVALID")
            return content

    claim = Claim(
        job_id=UUID(int=1),
        document_id=UUID(int=2),
        token=UUID(int=3),
        attempt=1,
        revision=1,
        course_id=UUID(int=4),
        file_type=".md",
        storage_path="synthetic.md",
        file_hash=hashlib.sha256(content).hexdigest(),
        byte_size=len(content),
    )
    document = await process_document(MemoryStorage(), claim)  # type: ignore[arg-type]
    require(bool(document.chunks), "INGEST_CHUNKS_MISSING")
    for vector in document.embeddings:
        validate_vector(vector)
    # İşlemin gerçek dönüş değeri RSS son gözlemi alınana dek referanslı tutulur.
    _RETAINED.append(document)
    return {
        "chunks": len(document.chunks),
        "vectors": len(document.embeddings),
        "batch_size": 32,
    }


async def api_lifecycle() -> dict[str, Any]:
    from app.core.warmup import warmup_state
    from app.main import app, lifespan
    from app.modules.ingestion.embedding import get_embedding_provider

    async with lifespan(app):
        while warmup_state() == "warming":  # noqa: ASYNC110 - üretim API durum yüzeyi Event sunmuyor
            await asyncio.sleep(0.01)
        require(warmup_state() == "ok", "API_WARMUP_FAILED")
        vector = await asyncio.to_thread(get_embedding_provider().embed_query, QUERY)
        validate_vector(vector)
        _RETAINED.append(app)
    return {"warmup_state": "ok", "vector_dimension": len(vector)}


def qint8_smoke(model: Path, tokenizer_path: Path) -> dict[str, Any]:
    import numpy as np
    import onnxruntime as ort
    from tokenizers import Tokenizer

    tokenizer = Tokenizer.from_file(str(tokenizer_path))
    tokenizer.enable_truncation(max_length=512)
    pad_id = tokenizer.token_to_id("<pad>")
    require(pad_id is not None, "QINT8_PAD_TOKEN_MISSING")
    # XLM-R dolgu simgesi; parola değildir.
    tokenizer.enable_padding(pad_id=pad_id, pad_token="<pad>")  # noqa: S106
    encoded = tokenizer.encode_batch(["query: " + QUERY, "passage: Sanal bellek adresleri eşler."])
    tensors = {
        "input_ids": np.asarray([item.ids for item in encoded], dtype=np.int64),
        "attention_mask": np.asarray([item.attention_mask for item in encoded], dtype=np.int64),
        "token_type_ids": np.asarray([item.type_ids for item in encoded], dtype=np.int64),
    }
    session = ort.InferenceSession(str(model), providers=["CPUExecutionProvider"])
    feeds = {item.name: tensors[item.name] for item in session.get_inputs()}
    outputs = session.run(None, feeds)
    require(bool(outputs), "QINT8_OUTPUT_MISSING")
    for output in outputs:
        require(bool(np.isfinite(output).all()), "QINT8_OUTPUT_NONFINITE")
    token_output = outputs[0]
    require(
        token_output.shape == (2, len(encoded[0].ids), 1024),
        "QINT8_OUTPUT_SHAPE_INVALID",
    )
    mask = tensors["attention_mask"][..., None]
    pooled = (token_output * mask).sum(axis=1) / mask.sum(axis=1)
    for vector in pooled:
        validate_vector(vector)
    _RETAINED.extend([session, tokenizer, outputs])
    return {
        "providers": session.get_providers(),
        "output_shapes": [list(item.shape) for item in outputs],
        "pooled_dimension": 1024,
        "finite": True,
        "production_provider_changed": False,
        "semantic_equivalence_evaluated": False,
    }


_RETAINED: list[Any] = []


def child_main(args: argparse.Namespace) -> int:
    """Protokol ayrı fd'de tutulur; uygulama/bağımlılık günlükleri dışarı aktarılmaz."""
    protocol = os.fdopen(os.dup(sys.stdout.fileno()), "w", buffering=1)
    null = os.open(os.devnull, os.O_WRONLY)
    os.dup2(null, sys.stdout.fileno())
    os.dup2(null, sys.stderr.fileno())
    os.close(null)
    network = NetworkGuard()
    sys.addaudithook(network.audit)

    def emit(event: str, **values: Any) -> None:
        protocol.write(json.dumps({"event": event, **values}, allow_nan=False) + "\n")

    def wait(command: str) -> None:
        require(sys.stdin.readline().strip() == command, "PARENT_COMMAND_INVALID")

    def phase(name: str, operation: Any) -> None:
        emit("phase_start", phase=name)
        wait("continue")
        began = time.monotonic_ns()
        detail = operation()
        detail.update(
            {
                "started_monotonic_ns": began,
                "finished_monotonic_ns": time.monotonic_ns(),
            }
        )
        require(network.attempts == 0, "NETWORK_ATTEMPT_OBSERVED")
        emit("phase_done", phase=name, detail=detail)
        wait("continue")

    source_before: str | None = None
    try:
        source_before = manifest_digest(source_manifest())
        sys.path.insert(0, str(ROOT / "apps/api"))
        from app.core import config

        settings = config.Settings(
            _env_file=None,
            environment="local",
            dev_auth_enabled=True,
            embedding_provider=args.provider,
            embedding_model=MODEL,
            embedding_cache_dir=str(args.cache_dir) if args.cache_dir else None,
            embedding_batch_size=32,
            embedding_warmup_enabled=True,
        )
        config.get_settings = lambda: settings
        from app.modules.ingestion.embedding import get_embedding_provider

        if args.child == "embedding":
            provider = get_embedding_provider()

            def query() -> dict[str, Any]:
                vector = provider.embed_query(QUERY)
                validate_vector(vector)
                return {"vector_dimension": len(vector)}

            phase("cold_query", query)
            phase("warm_query", query)
        elif args.child == "worker":
            # Worker modülünün ithal ettiği aynı işleme hattı ölçülür; DB claim/drain çağrılmaz.
            import app.worker

            phase("ingest", lambda: asyncio.run(prepare_document(args.paragraphs)))
        elif args.child == "api":
            import app.main  # noqa: F401

            phase("api_lifecycle", lambda: asyncio.run(api_lifecycle()))
        else:
            phase(
                "qint8_smoke",
                lambda: qint8_smoke(args.qint8_model, args.qint8_tokenizer),
            )
        require(network.attempts == 0, "NETWORK_ATTEMPT_OBSERVED")
        emit(
            "complete",
            network_attempts=network.attempts,
            blocked_local_ipv6_probe=network.blocked_local_ipv6_probe,
            source_digest_before=source_before,
            source_digest_after=manifest_digest(source_manifest()),
        )
        wait("stop")
        return 0
    except BaseException as exc:
        emit("error", **child_failure_diagnostics(exc, network, source_before))
        return 1
    finally:
        protocol.close()


def validate_args(args: argparse.Namespace) -> None:
    require(
        math.isfinite(args.timeout_seconds) and 1 <= args.timeout_seconds <= 3600,
        "TIMEOUT_INVALID",
    )
    require(10 <= args.interval_ms <= 1000, "INTERVAL_INVALID")
    require(64 <= args.rss_budget_mib <= 65536, "RSS_BUDGET_INVALID")
    require(1 <= args.paragraphs <= 512, "PARAGRAPHS_INVALID")
    require(
        bool(args.profiles)
        and len(args.profiles) == len(set(args.profiles))
        and set(args.profiles) <= {"query", "ingest", "combined", "qint8"},
        "PROFILES_INVALID",
    )
    require(
        (args.qint8_model is None) == (args.qint8_tokenizer is None),
        "QINT8_ARGUMENTS_INCOMPLETE",
    )
    for name in ("cache_dir", "qint8_model", "qint8_tokenizer"):
        value = getattr(args, name)
        if value is not None:
            setattr(args, name, value.resolve(strict=True))


def run(args: argparse.Namespace) -> dict[str, Any]:
    validate_args(args)
    source = source_manifest()
    needs_embedding = bool(set(args.profiles) & {"query", "ingest", "combined"})
    model = (
        model_manifest(args.cache_dir, args.provider)
        if needs_embedding
        else {"provider": "not-loaded", "model_files": {}}
    )
    qint8: dict[str, Any] = {
        "status": "not-run",
        "reason": "LOCAL_ARTIFACT_NOT_SUPPLIED",
        "upstream": QINT8_UPSTREAM,
    }
    if "qint8" in args.profiles and args.qint8_model is not None:
        qint8.update(
            {
                "reason": "PROFILE_NOT_STARTED",
                "model": file_digest(args.qint8_model),
                "tokenizer": file_digest(args.qint8_tokenizer),
            }
        )
        require(qint8["model"]["sha256"] == QINT8_SHA, "QINT8_UPSTREAM_HASH_MISMATCH")
    report: dict[str, Any] = {
        "schema_version": 1,
        "status": "running",
        "provider": args.provider,
        "scope": "API lifecycle + worker processing component RSS; no DB, HTTP or claim loop",
        "cold_definition": "fresh process/model session; OS file cache not flushed",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "platform": {
            "system": platform.system(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "versions": {
            name: importlib.metadata.version(name) for name in ("fastembed", "onnxruntime")
        },
        "source_before": source,
        "model_before": model,
        "workload": {
            "paragraphs": args.paragraphs,
            "sha256": hashlib.sha256(synthetic_document(args.paragraphs)).hexdigest(),
            "embedding_batch_size": 32,
        },
        "limits": {
            "timeout_seconds_per_group": args.timeout_seconds,
            "rss_budget_mib": args.rss_budget_mib,
            "sample_interval_ms": args.interval_ms,
        },
        "limitations": [
            "Sampled RSS is a lower bound and may miss short peaks.",
            "The RSS budget is sampled, not a kernel limit or a global headroom guarantee.",
            "Sum RSS can count shared pages twice.",
            "Hashing is harness mechanics, not E5 capacity evidence.",
            "No hosting/container or model-quality acceptance.",
            "All audited bind/connect/getaddrinfo operations remain blocked; no OS firewall claim.",
            "network_attempts counts rejected operations except the separately blocked exact "
            "IPv6 stream loopback ::1/port0 probe; measured groups require zero other attempts.",
            "blocked_local_ipv6_probe counts blocked capability probes, not permitted binds. "
            "Zero network_attempts does not mean zero socket attempts; "
            "missing child counters are null.",
        ],
        "groups": [],
        "requested_profiles": args.profiles,
        "not_run": [
            {"profile": name, "reason": "PROFILE_NOT_SELECTED"}
            for name in ("query", "ingest", "combined", "qint8")
            if name not in args.profiles
        ],
        "qint8": qint8,
    }
    try:
        with tempfile.TemporaryDirectory(prefix="dou-l4-rss-") as directory:
            work = Path(directory)
            for profile, roles in (
                ("query", ["embedding"]),
                ("ingest", ["worker"]),
                ("combined", ["api", "worker"]),
            ):
                if profile in args.profiles:
                    report["groups"].append(measure_group(args, roles, work))
            if "qint8" in args.profiles and args.qint8_model is not None:
                qint8["status"] = "running"
                qint8.pop("reason", None)
                qint8["measurement"] = measure_group(args, ["qint8"], work)
                require(
                    file_digest(args.qint8_model) == qint8["model"],
                    "QINT8_MODEL_CHANGED",
                )
                require(
                    file_digest(args.qint8_tokenizer) == qint8["tokenizer"],
                    "QINT8_TOKENIZER_CHANGED",
                )
                qint8["status"] = "measured"
                qint8.pop("reason", None)
            elif "qint8" in args.profiles:
                report["not_run"].append(
                    {"profile": "qint8", "reason": "LOCAL_ARTIFACT_NOT_SUPPLIED"}
                )
            else:
                qint8["reason"] = "PROFILE_NOT_SELECTED"
        require(
            bool(report["groups"]) or qint8["status"] == "measured",
            "NO_PROFILE_MEASURED",
        )
        report["complete_requested_profiles"] = not any(
            item["profile"] in args.profiles for item in report["not_run"]
        )
        report["source_after"] = source_manifest()
        report["model_after"] = (
            model_manifest(args.cache_dir, args.provider) if needs_embedding else model
        )
        require(report["source_after"] == source, "SOURCE_CHANGED")
        require(report["model_after"] == model, "MODEL_CHANGED")
        report["status"] = "measured"
    except Exception as exc:
        report["status"] = "failed"
        if hasattr(exc, "measurement"):
            report["failed_group"] = exc.measurement
        report["error"] = str(exc) if isinstance(exc, MeasurementError) else "MEASUREMENT_FAILED"
        if qint8["status"] == "running":
            qint8.update(
                {
                    "status": "failed",
                    "reason": "QINT8_SMOKE_FAILED",
                    "error": report["error"],
                }
            )
            if "failed_group" in report:
                qint8["measurement"] = report["failed_group"]
        elif qint8.get("reason") == "PROFILE_NOT_STARTED":
            report["not_run"].append({"profile": "qint8", "reason": "PROFILE_NOT_STARTED"})
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=("fastembed", "hashing"), default="fastembed")
    parser.add_argument(
        "--profiles",
        nargs="+",
        choices=("query", "ingest", "combined", "qint8"),
        default=["query", "ingest", "combined", "qint8"],
    )
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--qint8-model", type=Path)
    parser.add_argument("--qint8-tokenizer", type=Path)
    parser.add_argument("--paragraphs", type=int, default=32)
    parser.add_argument("--interval-ms", type=int, default=50)
    parser.add_argument("--timeout-seconds", type=float, default=600)
    parser.add_argument("--rss-budget-mib", type=int, default=8192)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--child",
        choices=("embedding", "worker", "api", "qint8"),
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args(argv)
    if args.child:
        return child_main(args)
    # Çıktı yolu modeli yüklemeden önce ayrılır; eski kanıt dosyası ezilmez.
    try:
        output = args.output.open("x", encoding="utf-8") if args.output is not None else None
    except OSError:
        print(
            json.dumps(
                {
                    "schema_version": 1,
                    "status": "failed",
                    "error": "OUTPUT_RESERVE_FAILED",
                }
            )
        )
        return 1
    try:
        result = run(args)
    except Exception as exc:
        result = {
            "schema_version": 1,
            "status": "failed",
            "error": str(exc) if isinstance(exc, MeasurementError) else "PREFLIGHT_FAILED",
        }
    encoded = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if output is not None:
        try:
            with output:
                output.write(encoded)
        except OSError:
            # Kısmi/başarısız dosya yazımı ölçüm gözlemlerini stdout'tan silmez.
            result["output_error"] = "OUTPUT_WRITE_FAILED"
            print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
            return 1
    print(encoded)
    return 0 if result["status"] == "measured" else 1


if __name__ == "__main__":
    raise SystemExit(main())
