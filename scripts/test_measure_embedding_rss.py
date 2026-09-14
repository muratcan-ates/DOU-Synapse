"""Ölçücünün çevrimdışı mekanik ve hata kontrolleri; E5 kapasite kanıtı değildir."""

from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Self, TextIO

import pytest

from scripts import measure_embedding_rss as target


def arguments(**overrides: object) -> argparse.Namespace:
    values = {
        "provider": "hashing",
        "profiles": ["query", "ingest", "combined", "qint8"],
        "cache_dir": None,
        "qint8_model": None,
        "qint8_tokenizer": None,
        "paragraphs": 1,
        "interval_ms": 100,
        "timeout_seconds": 120.0,
        "rss_budget_mib": 4096,
    }
    return argparse.Namespace(**(values | overrides))


def test_rss_conversion_requires_every_owned_pid_once() -> None:
    assert target.parse_rss(" 11 1024\n12 2048\n", {11, 12}) == {
        11: 1024 * 1024,
        12: 2 * 1024 * 1024,
    }


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "11 12\n",
        "11 1\n11 2\n",
        "11 1\n13 1\n",
        "11 0\n12 3\n",
        "11 NaN\n12 1\n",
        "11 1 extra\n12 2\n",
    ],
)
def test_missing_or_invalid_observation_never_becomes_zero(raw: str) -> None:
    with pytest.raises(target.MeasurementError):
        target.parse_rss(raw, {11, 12})


def test_aggregate_uses_common_sample_not_individual_peaks() -> None:
    samples = [
        {
            "rss_bytes": {"1": 900, "2": 100},
            "sum_rss_bytes": 1000,
            "started_monotonic_ns": 1,
        },
        {
            "rss_bytes": {"1": 100, "2": 800},
            "sum_rss_bytes": 900,
            "started_monotonic_ns": 2,
        },
    ]
    result = target.aggregate(samples)
    assert result["peak_sum_rss_bytes"] == 1000
    assert result["peak"]["started_monotonic_ns"] == 1
    with pytest.raises(target.MeasurementError, match="NO_RSS_SAMPLES"):
        target.aggregate([])


@pytest.mark.parametrize(
    "result",
    [
        SimpleNamespace(returncode=1, stdout="private-marker"),
        SimpleNamespace(returncode=0, stdout=""),
    ],
)
def test_observer_rejection_is_fixed_and_does_not_echo_output(
    monkeypatch: pytest.MonkeyPatch, result: object
) -> None:
    monkeypatch.setattr(target.subprocess, "run", lambda *args, **kwargs: result)
    with pytest.raises(target.MeasurementError) as error:
        target.observe({123})
    assert "private-marker" not in str(error.value)


def test_observer_timeout_is_fixed(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise subprocess.TimeoutExpired("private-marker", 1)

    monkeypatch.setattr(target.subprocess, "run", fail)
    with pytest.raises(target.MeasurementError, match=r"^RSS_OBSERVER_FAILED$"):
        target.observe({123})


@pytest.mark.parametrize(
    "changes",
    [
        {"timeout_seconds": float("nan")},
        {"timeout_seconds": float("inf")},
        {"timeout_seconds": 0},
        {"rss_budget_mib": 0},
        {"interval_ms": 0},
        {"paragraphs": 0},
        {"qint8_model": Path("missing")},
    ],
)
def test_finite_bounds_and_complete_qint8_arguments(changes: dict[str, object]) -> None:
    with pytest.raises(target.MeasurementError):
        target.validate_args(arguments(**changes))


def test_clean_child_environment_excludes_ambient_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "synthetic-private-marker")
    monkeypatch.setenv("DATABASE_URL", "synthetic-private-marker")
    environment = target.clean_environment(tmp_path)
    assert "synthetic-private-marker" not in json.dumps(environment)
    assert "GROQ_API_KEY" not in environment and "DATABASE_URL" not in environment
    assert environment["HF_HUB_OFFLINE"] == "1"


def test_missing_cached_model_cannot_start_a_download(tmp_path: Path) -> None:
    with pytest.raises(target.MeasurementError, match="SINGLE_PINNED_SNAPSHOT_REQUIRED"):
        target.model_manifest(tmp_path, "fastembed")


def test_observer_failure_stops_and_waits_owned_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_popen = subprocess.Popen
    children = []

    def launch(*args: object, **kwargs: object) -> subprocess.Popen[bytes]:
        child = real_popen([sys.executable, "-c", "import time; time.sleep(30)"], **kwargs)
        children.append(child)
        return child

    def fail(_pids: object) -> None:
        raise target.MeasurementError("RSS_OBSERVER_FAILED")

    monkeypatch.setattr(target.subprocess, "Popen", launch)
    monkeypatch.setattr(target, "observe", fail)
    with pytest.raises(target.MeasurementError, match="RSS_OBSERVER_FAILED") as error:
        target.measure_group(arguments(), ["embedding"], tmp_path)
    assert len(children) == 1 and children[0].poll() is not None
    assert error.value.measurement["cleanup"]["embedding"]["reaped"] is True


def test_rss_budget_stops_child_before_long_operation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_popen = subprocess.Popen
    children = []

    def launch(*args: object, **kwargs: object) -> subprocess.Popen[bytes]:
        child = real_popen([sys.executable, "-c", "import time; time.sleep(30)"], **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(target.subprocess, "Popen", launch)
    monkeypatch.setattr(
        target,
        "observe",
        lambda pids: {
            "rss_bytes": {str(pid): 65 * target.MIB for pid in pids},
            "sum_rss_bytes": 65 * target.MIB,
        },
    )
    with pytest.raises(target.MeasurementError, match="RSS_BUDGET_EXCEEDED"):
        target.measure_group(arguments(rss_budget_mib=64), ["embedding"], tmp_path)
    assert children[0].poll() is not None


def test_hashing_runs_real_ingestion_and_concurrent_lifecycle_offline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "synthetic-private-marker")
    result = target.run(arguments())
    assert result["status"] == "measured", result.get("error")
    assert result["source_before"] == result["source_after"]
    assert result["model_before"] == result["model_after"]
    assert result["qint8"]["status"] == "not-run"
    assert "synthetic-private-marker" not in json.dumps(result)
    solo, ingest, combined = result["groups"]
    assert [item["phase"] for item in solo["phases"]] == ["cold_query", "warm_query"]
    assert ingest["phases"][0]["detail"]["chunks"] >= 1
    assert combined["roles"] == ["api", "worker"]
    assert combined["network_attempts"] == 0
    assert combined["blocked_local_ipv6_probe"] == sum(
        combined["blocked_local_ipv6_probe_by_role"].values()
    )
    assert all(
        type(count) is int for count in combined["blocked_local_ipv6_probe_by_role"].values()
    )
    assert all(value["reaped"] for value in combined["cleanup"].values())
    assert combined["source_manifest_digest"] == target.manifest_digest(result["source_before"])
    assert len(set(combined["pids"].values())) == 2
    assert all(code == 0 for code in combined["exit_codes"].values())
    assert any(set(item["phases"]) == {"api", "worker"} for item in combined["observations"])
    assert all(
        set(item["rss_bytes"]) == {str(pid) for pid in combined["pids"].values()}
        for item in combined["observations"]
    )


def test_cli_preflight_failure_returns_nonzero_without_model_load(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert target.main(["--provider", "fastembed"]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "failed" and result["error"] == "CACHE_REQUIRED"


@pytest.mark.parametrize(
    "event",
    ["socket.connect", "socket.connect_ex", "socket.bind", "socket.getaddrinfo"],
)
def test_network_guard_counts_and_rejects_attempts(event: str) -> None:
    guard = target.NetworkGuard()
    guard.audit("open", ())
    assert guard.attempts == 0
    with pytest.raises(target.MeasurementError, match="NETWORK_FORBIDDEN"):
        guard.audit(event, ("synthetic-secret-marker",))
    assert guard.attempts == 1


def test_qint8_only_missing_artifact_is_not_a_success() -> None:
    result = target.run(arguments(profiles=["qint8"]))
    assert result["status"] == "failed" and result["error"] == "NO_PROFILE_MEASURED"
    assert result["model_before"]["provider"] == "not-loaded"
    assert any(item["profile"] == "qint8" for item in result["not_run"])


@pytest.fixture
def synthetic_qint8_arguments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> argparse.Namespace:
    model = tmp_path / "synthetic-model.onnx"
    tokenizer = tmp_path / "synthetic-tokenizer.json"
    model.write_bytes(b"synthetic model placeholder; not an ONNX artifact")
    tokenizer.write_text("{}")
    # Yalnız rapor durum makinesini sınar; bu sahte özetler ölçüm kanıtı değildir.
    monkeypatch.setattr(
        target, "file_digest", lambda path: {"sha256": target.QINT8_SHA, "bytes": 1}
    )
    return arguments(profiles=["qint8"], qint8_model=model, qint8_tokenizer=tokenizer)


def test_qint8_attempt_failure_is_failed_and_preserves_observation_cleanup(
    synthetic_qint8_arguments: argparse.Namespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    evidence = {
        "roles": ["qint8"],
        "observations": [{"rss_bytes": {"123": 1024}, "sum_rss_bytes": 1024}],
        "cleanup": {"qint8": {"pid": 123, "returncode": 1, "reaped": True}},
    }

    def fail(args: object, roles: list[str], work: Path) -> None:
        assert roles == ["qint8"]
        error = target.MeasurementError("CHILD_REPORTED_FAILURE")
        error.measurement = evidence
        raise error

    monkeypatch.setattr(target, "measure_group", fail)
    result = target.run(synthetic_qint8_arguments)
    assert result["status"] == "failed"
    assert result["qint8"]["status"] == "failed"
    assert result["qint8"]["reason"] == "QINT8_SMOKE_FAILED"
    assert result["qint8"]["error"] == "CHILD_REPORTED_FAILURE"
    assert result["qint8"]["measurement"] is result["failed_group"]
    assert result["qint8"]["measurement"] == evidence
    assert all(item["profile"] != "qint8" for item in result["not_run"])


def test_qint8_artifact_present_but_earlier_profile_failed_stays_not_run(
    synthetic_qint8_arguments: argparse.Namespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    synthetic_qint8_arguments.profiles = ["query", "qint8"]

    def fail(args: object, roles: list[str], work: Path) -> None:
        assert roles == ["embedding"]
        raise target.MeasurementError("RSS_OBSERVER_FAILED")

    monkeypatch.setattr(target, "measure_group", fail)
    result = target.run(synthetic_qint8_arguments)
    assert result["status"] == "failed"
    assert result["qint8"]["status"] == "not-run"
    assert result["qint8"]["reason"] == "PROFILE_NOT_STARTED"
    assert "measurement" not in result["qint8"]


@pytest.mark.parametrize("obstacle", ["existing-file", "missing-parent"])
def test_output_reservation_failure_cannot_start_measurement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    obstacle: str,
) -> None:
    output = tmp_path / "observation.json"
    if obstacle == "existing-file":
        output.write_text("previous evidence\n")
    else:
        output = tmp_path / "missing-parent" / "observation.json"

    def forbidden_run(_args: argparse.Namespace) -> dict[str, object]:
        pytest.fail("Output reservation failure must not reach model loading or child execution")

    monkeypatch.setattr(target, "run", forbidden_run)
    assert target.main(["--output", str(output)]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result == {
        "schema_version": 1,
        "status": "failed",
        "error": "OUTPUT_RESERVE_FAILED",
    }
    if obstacle == "existing-file":
        assert output.read_text() == "previous evidence\n"
    else:
        assert not output.parent.exists()


def test_output_is_reserved_before_measurement_and_contains_complete_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "observation.json"
    evidence = {
        "schema_version": 1,
        "status": "measured",
        "groups": [{"observations": [{"sum_rss_bytes": 1024}], "cleanup": {"reaped": True}}],
    }

    def measured(_args: argparse.Namespace) -> dict[str, object]:
        assert output.is_file() and output.read_text() == ""
        return evidence

    monkeypatch.setattr(target, "run", measured)
    assert target.main(["--output", str(output)]) == 0
    assert json.loads(output.read_text()) == evidence
    assert json.loads(capsys.readouterr().out) == evidence


@pytest.mark.parametrize("failure_phase", ["write", "close"])
def test_final_output_failure_retains_complete_observation_on_stdout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failure_phase: str,
) -> None:
    output = tmp_path / "observation.json"
    real_open = Path.open
    reserved_streams = []
    evidence = {
        "schema_version": 1,
        "status": "failed",
        "error": "CHILD_REPORTED_FAILURE",
        "failed_group": {
            "roles": ["qint8"],
            "observations": [{"rss_bytes": {"123": 1024}, "sum_rss_bytes": 1024}],
            "cleanup": {"qint8": {"pid": 123, "returncode": 1, "reaped": True}},
        },
    }

    class BrokenOutput:
        def __init__(self, stream: TextIO) -> None:
            self.stream = stream

        def __enter__(self) -> Self:
            return self

        def __exit__(self, *args: object) -> None:
            self.stream.close()
            if failure_phase == "close":
                raise OSError("synthetic-private-filesystem-marker")

        def write(self, encoded: str) -> None:
            if failure_phase == "write":
                self.stream.write(encoded[:20])
                raise OSError("synthetic-private-filesystem-marker")
            self.stream.write(encoded)

    def reserve(path: Path, *args: object, **kwargs: object) -> object:
        stream = real_open(path, *args, **kwargs)
        if path == output:
            assert args == ("x",)
            reserved_streams.append(stream)
            return BrokenOutput(stream)
        return stream

    def measured(_args: argparse.Namespace) -> dict[str, object]:
        assert output.exists() and len(reserved_streams) == 1
        return dict(evidence)

    monkeypatch.setattr(Path, "open", reserve)
    monkeypatch.setattr(target, "run", measured)
    assert target.main(["--output", str(output)]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result == {**evidence, "output_error": "OUTPUT_WRITE_FAILED"}
    assert "synthetic-private-filesystem-marker" not in json.dumps(result)
    assert reserved_streams[0].closed


@pytest.mark.parametrize(
    ("error", "code", "category"),
    [
        (
            MemoryError("synthetic-private-marker"),
            "CHILD_OPERATION_FAILED",
            "MEMORY_ERROR",
        ),
        (
            ValueError("synthetic-private-marker"),
            "CHILD_OPERATION_FAILED",
            "VALUE_ERROR",
        ),
        (
            target.MeasurementError("NETWORK_FORBIDDEN"),
            "NETWORK_FORBIDDEN",
            "MEASUREMENT_ERROR",
        ),
        (
            target.MeasurementError("synthetic-private-marker"),
            "CHILD_OPERATION_FAILED",
            "MEASUREMENT_ERROR",
        ),
    ],
)
def test_child_failure_emits_only_allowlisted_diagnostics(
    monkeypatch: pytest.MonkeyPatch, error: BaseException, code: str, category: str
) -> None:
    monkeypatch.setattr(target, "source_manifest", lambda: {"synthetic_source": "unchanged"})
    digest = target.manifest_digest(target.source_manifest())
    network = target.NetworkGuard()
    with pytest.raises(target.MeasurementError):
        network.audit("socket.connect", ("synthetic-private-marker",))
    result = target.child_failure_diagnostics(error, network, digest)
    assert result == {
        "code": code,
        "exception_category": category,
        "network_attempts": 1,
        "blocked_local_ipv6_probe": 0,
        "source_digest_before": digest,
        "source_digest_after": digest,
    }
    assert "synthetic-private-marker" not in json.dumps(result)


def test_unknown_exception_class_and_unreadable_source_are_not_disclosed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class PrivateFailure(Exception):
        def __str__(self) -> str:
            pytest.fail("Failure reporting must never format an exception")

    def unreadable() -> dict[str, object]:
        raise OSError("synthetic-private-marker")

    monkeypatch.setattr(target, "source_manifest", unreadable)
    result = target.child_failure_diagnostics(PrivateFailure(), target.NetworkGuard(), None)
    assert result["code"] == "CHILD_OPERATION_FAILED"
    assert result["exception_category"] == "UNCLASSIFIED_ERROR"
    assert result["source_digest_before"] is None
    assert result["source_digest_after"] is None
    assert "PrivateFailure" not in json.dumps(result)
    assert "synthetic-private-marker" not in json.dumps(result)


@pytest.mark.parametrize(
    "corruption",
    [
        {"code": "synthetic-private-marker"},
        {"code": ["synthetic-private-marker"]},
        {"exception_category": "synthetic-private-marker"},
        {"network_attempts": "synthetic-private-marker"},
        {"network_attempts": True},
        {"network_attempts": -1},
        {"blocked_local_ipv6_probe": -1},
        {"blocked_local_ipv6_probe": True},
        {"blocked_local_ipv6_probe": "synthetic-private-marker"},
        {"source_digest_after": "synthetic-private-marker"},
        {"message": "synthetic-private-marker"},
    ],
)
def test_parent_rejects_unsafe_child_diagnostics_and_still_reaps_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, corruption: dict[str, object]
) -> None:
    payload = {
        "event": "error",
        "code": "CHILD_OPERATION_FAILED",
        "exception_category": "MEMORY_ERROR",
        "network_attempts": 0,
        "blocked_local_ipv6_probe": 0,
        "source_digest_before": None,
        "source_digest_after": None,
        **corruption,
    }
    real_popen = subprocess.Popen
    children = []

    def launch(command: list[str], **kwargs: object) -> subprocess.Popen[bytes]:
        if "--child" not in command:
            return real_popen(command, **kwargs)
        program = (
            "import time; print(" + repr(json.dumps(payload)) + ", flush=True); time.sleep(30)"
        )
        child = real_popen([sys.executable, "-c", program], **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(target.subprocess, "Popen", launch)
    with pytest.raises(target.MeasurementError, match=r"^CHILD_PROTOCOL_INVALID$") as error:
        target.measure_group(arguments(), ["embedding"], tmp_path)
    measurement = error.value.measurement
    assert measurement["child_failures"] == {}
    assert measurement["network_attempts_by_role"] == {"embedding": None}
    assert measurement["network_attempts"] is None
    assert measurement["cleanup"]["embedding"]["reaped"] is True
    assert children[0].poll() is not None
    assert "synthetic-private-marker" not in json.dumps(measurement)


@pytest.mark.parametrize("roles", [["embedding"], ["api", "worker"]])
def test_parent_retains_validated_child_failure_after_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, roles: list[str]
) -> None:
    digest = target.manifest_digest(target.source_manifest())
    payload = {
        "event": "error",
        "code": "NETWORK_FORBIDDEN",
        "exception_category": "MEASUREMENT_ERROR",
        "network_attempts": 1,
        "blocked_local_ipv6_probe": 0,
        "source_digest_before": digest,
        "source_digest_after": digest,
    }
    failing_role = roles[-1]
    real_popen = subprocess.Popen
    children = []

    def launch(command: list[str], **kwargs: object) -> subprocess.Popen[bytes]:
        if "--child" not in command:
            return real_popen(command, **kwargs)
        role = command[command.index("--child") + 1]
        program = "import time; time.sleep(30)"
        if role == failing_role:
            program = (
                "import time; print(" + repr(json.dumps(payload)) + ", flush=True); time.sleep(30)"
            )
        child = real_popen([sys.executable, "-c", program], **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(target.subprocess, "Popen", launch)
    with pytest.raises(target.MeasurementError, match=r"^CHILD_REPORTED_FAILURE$") as error:
        target.measure_group(arguments(), roles, tmp_path)
    measurement = error.value.measurement
    assert measurement["child_failures"] == {
        failing_role: {key: value for key, value in payload.items() if key != "event"}
    }
    assert measurement["source_manifest_digest"] == digest
    assert measurement["network_attempts_by_role"] == {
        role: 1 if role == failing_role else None for role in roles
    }
    assert measurement["network_attempts"] == (1 if len(roles) == 1 else None)
    assert measurement["blocked_local_ipv6_probe"] == (0 if len(roles) == 1 else None)
    assert measurement["observations"]
    assert all(item["reaped"] for item in measurement["cleanup"].values())
    assert all(child.poll() is not None for child in children)


def test_child_process_reports_failure_counter_without_private_error_text(
    tmp_path: Path,
) -> None:
    program = (
        "import sys; from types import SimpleNamespace; "
        f"sys.path.insert(0, {str(target.ROOT)!r}); "
        "from scripts import measure_embedding_rss as target; "
        "target.source_manifest = lambda: "
        "sys.audit('socket.connect', ('synthetic-private-marker',)); "
        "sys.exit(target.child_main(SimpleNamespace(child='embedding')))"
    )
    result = subprocess.run(  # noqa: S603 - sabit çevrimdışı test programı
        [sys.executable, "-c", program],
        capture_output=True,
        text=True,
        timeout=10,
        cwd=tmp_path,
        env=target.clean_environment(tmp_path),
        check=False,
    )
    assert result.returncode == 1
    event = json.loads(result.stdout)
    assert event["event"] == "error"
    assert event["code"] == "NETWORK_FORBIDDEN"
    assert event["exception_category"] == "MEASUREMENT_ERROR"
    # İlk kaynak okuması ve hata sonrası kaynak denetimi ayrı ayrı engellenir.
    assert event["network_attempts"] == 2
    assert event["blocked_local_ipv6_probe"] == 0
    assert event["source_digest_before"] is None
    assert event["source_digest_after"] is None
    assert result.stderr == ""
    assert "synthetic-private-marker" not in result.stdout


@pytest.mark.parametrize(
    ("module", "name", "category"),
    [
        ("onnxruntime.capi.onnxruntime_pybind11_state", "Fail", "ONNX_FAIL"),
        ("onnxruntime.capi.onnxruntime_pybind11_state", "InvalidArgument", "ONNX_INVALID_ARGUMENT"),
        ("onnxruntime.capi.onnxruntime_pybind11_state", "RuntimeException", "ONNX_RUNTIME_ERROR"),
        ("onnxruntime.capi.onnxruntime_pybind11_state", "NoSuchFile", "ONNX_FILE_NOT_FOUND"),
        ("onnxruntime.capi.onnxruntime_pybind11_state", "InvalidGraph", "ONNX_INVALID_GRAPH"),
        ("onnxruntime.capi.onnxruntime_pybind11_state", "NotImplemented", "ONNX_NOT_IMPLEMENTED"),
        ("onnxruntime.capi.onnxruntime_pybind11_state", "EPFail", "ONNX_PROVIDER_ERROR"),
        ("synthetic-private-marker", "Fail", "UNCLASSIFIED_ERROR"),
    ],
)
def test_onnx_failure_category_requires_exact_module_and_class(
    monkeypatch: pytest.MonkeyPatch, module: str, name: str, category: str
) -> None:
    # Tür eşleme sözleşmesi; ONNX veya model yüklemesi yapılmaz.
    error_type = type(name, (Exception,), {"__module__": module})
    monkeypatch.setattr(target, "source_manifest", lambda: {})
    result = target.child_failure_diagnostics(
        error_type("synthetic-private-marker"), target.NetworkGuard(), None
    )
    assert result["exception_category"] == category
    assert result["code"] == "CHILD_OPERATION_FAILED"
    assert "synthetic-private-marker" not in json.dumps(result)


@pytest.mark.parametrize("address", [("::1", 0), ("::1", 0, 0), ("::1", 0, 0, 0)])
def test_exact_ipv6_loopback_probe_is_counted_separately_but_still_blocked(
    address: tuple[object, ...],
) -> None:
    guard = target.NetworkGuard()
    with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as sock:
        with pytest.raises(target.MeasurementError, match=r"^NETWORK_FORBIDDEN$"):
            guard.audit("socket.bind", (sock, address))
    assert guard.attempts == 0
    assert guard.blocked_local_ipv6_probe == 1


@pytest.mark.parametrize(
    "address",
    [
        ("::1", 1),
        ("::1", -1),
        ("::1", False),
        ("::1", "0"),
        ("::1", 0, 1),
        ("::1", 0, 0, 1),
        ("::1", 0, False),
        ("::1", 0, 0, False),
        ("::1", 0, 0, 0, 0),
        ("::", 0),
        ("2001:db8::1", 0),
        ("127.0.0.1", 0),
        ("::ffff:127.0.0.1", 0),
        ("::1%synthetic", 0),
        ["::1", 0],
    ],
)
def test_other_bind_addresses_ports_and_scope_are_forbidden(address: object) -> None:
    guard = target.NetworkGuard()
    with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as sock:
        with pytest.raises(target.MeasurementError, match=r"^NETWORK_FORBIDDEN$"):
            guard.audit("socket.bind", (sock, address))
    assert guard.attempts == 1
    assert guard.blocked_local_ipv6_probe == 0


@pytest.mark.parametrize(
    ("family", "kind"),
    [(socket.AF_INET, socket.SOCK_STREAM), (socket.AF_INET6, socket.SOCK_DGRAM)],
)
def test_probe_shape_requires_ipv6_stream_socket(family: int, kind: int) -> None:
    guard = target.NetworkGuard()
    with socket.socket(family, kind) as sock:
        with pytest.raises(target.MeasurementError, match=r"^NETWORK_FORBIDDEN$"):
            guard.audit("socket.bind", (sock, ("::1", 0)))
    assert guard.attempts == 1
    assert guard.blocked_local_ipv6_probe == 0


@pytest.mark.parametrize("event", ["socket.connect", "socket.connect_ex", "socket.getaddrinfo"])
def test_loopback_shape_does_not_exempt_any_other_socket_operation(event: str) -> None:
    guard = target.NetworkGuard()
    with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as sock:
        with pytest.raises(target.MeasurementError, match=r"^NETWORK_FORBIDDEN$"):
            guard.audit(event, (sock, ("::1", 0)))
    assert guard.attempts == 1
    assert guard.blocked_local_ipv6_probe == 0


def test_real_bind_remains_blocked_and_urllib3_import_handles_the_probe(tmp_path: Path) -> None:
    program = (
        "import json, socket, sys; "
        f"sys.path.insert(0, {str(target.ROOT)!r}); "
        "from scripts import measure_embedding_rss as target; "
        "guard=target.NetworkGuard(); sys.addaudithook(guard.audit); "
        "sock=socket.socket(socket.AF_INET6, socket.SOCK_STREAM)\n"
        "try: sock.bind(('::1', 0))\n"
        "except target.MeasurementError: pass\n"
        "else: raise AssertionError('bind must remain blocked')\n"
        "port=sock.getsockname()[1]; sock.close()\n"
        "import urllib3.util.connection\n"
        "print(json.dumps({'port':port,'has_ipv6':urllib3.util.connection.HAS_IPV6,"
        "'network_attempts':guard.attempts,'blocked_local_ipv6_probe':guard.blocked_local_ipv6_probe}))"
    )
    result = subprocess.run(  # noqa: S603 - sabit yerel yoklama testi, model yüklenmez
        [sys.executable, "-c", program],
        capture_output=True,
        text=True,
        timeout=10,
        cwd=tmp_path,
        env=target.clean_environment(tmp_path),
        check=False,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout) == {
        "port": 0,
        "has_ipv6": False,
        "network_attempts": 0,
        "blocked_local_ipv6_probe": 2,
    }
    assert result.stderr == ""


def test_local_probe_counter_survives_child_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(target, "source_manifest", lambda: {})
    guard = target.NetworkGuard()
    with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as sock:
        with pytest.raises(target.MeasurementError):
            guard.audit("socket.bind", (sock, ("::1", 0)))
    result = target.child_failure_diagnostics(ValueError("synthetic-private-marker"), guard, None)
    assert result["network_attempts"] == 0
    assert result["blocked_local_ipv6_probe"] == 1
    assert "synthetic-private-marker" not in json.dumps(result)


def test_child_exit_timeout_has_fixed_code_and_preserves_completed_counters(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    digest = target.manifest_digest(target.source_manifest())
    payload = {
        "event": "complete",
        "network_attempts": 0,
        "blocked_local_ipv6_probe": 1,
        "source_digest_before": digest,
        "source_digest_after": digest,
    }
    real_popen = subprocess.Popen
    children = []

    def launch(command: list[str], **kwargs: object) -> subprocess.Popen[bytes]:
        if "--child" not in command:
            return real_popen(command, **kwargs)
        program = (
            "import sys; print(" + repr(json.dumps(payload)) + ", flush=True); sys.stdin.readline()"
        )
        child = real_popen([sys.executable, "-c", program], **kwargs)
        real_wait = child.wait
        timed_out = False

        def timeout_once(timeout: float | None = None) -> int:
            nonlocal timed_out
            assert timeout == 5, "The five-second exit boundary must not be relaxed"
            if not timed_out:
                timed_out = True
                raise subprocess.TimeoutExpired("synthetic-private-marker", 5)
            return real_wait(timeout=timeout)

        child.wait = timeout_once
        children.append(child)
        return child

    monkeypatch.setattr(target.subprocess, "Popen", launch)
    with pytest.raises(target.MeasurementError, match=r"^CHILD_EXIT_TIMEOUT$") as error:
        target.measure_group(arguments(), ["embedding"], tmp_path)
    measurement = error.value.measurement
    assert measurement["completed_roles"] == ["embedding"]
    assert measurement["network_attempts"] == 0
    assert measurement["blocked_local_ipv6_probe"] == 1
    assert measurement["blocked_local_ipv6_probe_by_role"] == {"embedding": 1}
    assert measurement["cleanup"]["embedding"]["reaped"] is True
    assert children[0].poll() is not None
    assert "synthetic-private-marker" not in json.dumps(measurement)
