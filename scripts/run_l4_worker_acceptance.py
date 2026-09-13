"""Sabitlenmiş yerel D3 başlatıcısı; pytest öncesinde mevcut veritabanını reddeder.

Özel ayarlar ve günlükler kullanıcıya ait 0700 izinli dizinde kalır. Paylaşılabilir
JSON yalnız kaynak özetlerini, sabit sonuçları ve JUnit sayılarını içerir;
veritabanı bağlantı bilgilerini veya ham günlükleri içermez.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import select
import signal
import stat
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from uuid import uuid4

import psycopg
from sqlalchemy.engine import make_url

SYSTEM_IDENTIFIER = "7685014034241297379"
PG_BIN = "/opt/homebrew/opt/postgresql@16/bin"
ROOT = Path(__file__).resolve().parents[1]
TEST = "scripts/test_worker_process_acceptance.py"
ANCHOR = "scripts/l4_worker_group_anchor.py"


class ProbeError(Exception):
    """Paylaşılabilir kayda yalnız sabit doğrulama kodları aktarılır."""


class AnchorOwnershipLost(ProbeError):
    """Çıpa kaybolduktan sonra aynı sayısal süreç grubuna tekrar sinyal verilmez."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ProbeError(code)


def source_hashes() -> dict[str, str]:
    paths = sorted((ROOT / "apps/api/app").rglob("*.py"))
    paths.extend(
        [
            ROOT / "scripts/l4_worker_signal_child.py",
            ROOT / "scripts/run_l4_worker_acceptance.py",
            ROOT / TEST,
            ROOT / ANCHOR,
        ]
    )
    return {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths
    }


def private_settings(path: Path) -> tuple[dict[str, Any], dict[str, str]]:
    require(not path.is_symlink(), "PRIVATE_CONFIG_SYMLINK")
    metadata = path.stat()
    require(stat.S_ISREG(metadata.st_mode), "PRIVATE_CONFIG_NOT_FILE")
    require(metadata.st_uid == os.getuid(), "PRIVATE_CONFIG_OWNER")
    require(stat.S_IMODE(metadata.st_mode) == 0o600, "PRIVATE_CONFIG_MODE")
    require(path.parent.stat().st_uid == os.getuid(), "PRIVATE_DIRECTORY_OWNER")
    require(stat.S_IMODE(path.parent.stat().st_mode) == 0o700, "PRIVATE_DIRECTORY_MODE")
    values = json.loads(path.read_text())
    database = values["database_name"]
    require(
        bool(re.fullmatch(r"dou_l4_d3_[0-9]{8}_[0-9]{6}_[a-f0-9]{8}", database)), "DATABASE_NAME"
    )
    urls = {}
    for key, username in (
        ("admin_dsn", "dou_l4_admin"),
        ("app_dsn", "dou_app"),
        ("worker_dsn", "dou_worker"),
    ):
        url = make_url(values[key])
        require(
            url.drivername == "postgresql+psycopg"
            and url.host == "127.0.0.1"
            and url.port == 55484
            and url.database == database
            and url.username == username
            and bool(url.password)
            and not url.query,
            "DATABASE_TARGET",
        )
        urls[key] = url
    admin = urls["admin_dsn"]
    admin_connection = admin.set(drivername="postgresql", database="postgres").render_as_string(
        hide_password=False
    )
    with psycopg.connect(admin_connection, connect_timeout=5, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT system_identifier::text, current_setting('data_directory'), "
                "host(inet_server_addr()), inet_server_port(), current_database(), current_user "
                "FROM pg_control_system()"
            )
            system, directory, address, port, connected_db, username = cursor.fetchone()
            require(system == SYSTEM_IDENTIFIER, "CLUSTER_SYSTEM_IDENTIFIER")
            require(
                Path(directory).resolve() == Path(values["data_directory"]).resolve(strict=True),
                "CLUSTER_DIRECTORY",
            )
            require(
                (address, port, connected_db, username)
                == ("127.0.0.1", 55484, "postgres", "dou_l4_admin"),
                "CLUSTER_ENDPOINT",
            )
            cursor.execute("SELECT EXISTS(SELECT 1 FROM pg_database WHERE datname=%s)", (database,))
            require(cursor.fetchone()[0] is False, "DATABASE_MUST_BE_NEW")
    environment = {
        "PATH": f"{PG_BIN}:/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "PYTHONPATH": str(ROOT / "apps/api"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PG_BIN": PG_BIN,
        "PGHOST": "127.0.0.1",
        "PGPORT": "55484",
        "PGUSER": "dou_l4_admin",
        "PGPASSWORD": admin.password,
        "TEST_DB_NAME": database,
        "TEST_ADMIN_DSN": values["admin_dsn"],
        "TEST_APP_DSN": values["app_dsn"],
        "TEST_WORKER_DSN": values["worker_dsn"],
        "EMBEDDING_PROVIDER": "hashing",
        "GROQ_API_KEY": "",
        "GEMINI_API_KEY": "",
        "OPENAI_API_KEY": "",
        "HF_HUB_OFFLINE": "1",
        "HF_HUB_DISABLE_TELEMETRY": "1",
        "LITELLM_LOCAL_MODEL_COST_MAP": "True",
        "DO_NOT_TRACK": "1",
        "DOU_L4_D3_PREFLIGHT": "owned-new-database-verified",
    }
    return values, environment


class AnchorProtocol:
    """Özel boruyu süre ve boyut sınırıyla, eksik satırda bloklamadan okur."""

    def __init__(self, descriptor: int) -> None:
        self.descriptor = descriptor
        self.buffer = bytearray()

    def read(self, timeout: float) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        while b"\n" not in self.buffer:
            remaining = deadline - time.monotonic()
            require(remaining > 0, "ANCHOR_PROTOCOL_TIMEOUT")
            readable, _, _ = select.select([self.descriptor], [], [], remaining)
            require(bool(readable), "ANCHOR_PROTOCOL_TIMEOUT")
            data = os.read(self.descriptor, 4096)
            require(bool(data), "ANCHOR_PROTOCOL_CLOSED")
            self.buffer.extend(data)
            require(len(self.buffer) <= 8192, "ANCHOR_PROTOCOL_SIZE")
        line, _, trailing = self.buffer.partition(b"\n")
        self.buffer = bytearray(trailing)
        value = json.loads(line)
        require(isinstance(value, dict), "ANCHOR_PROTOCOL_OBJECT")
        return value


def pin_anchor(process: subprocess.Popen[bytes]) -> int:
    """Yeni oturumun ve grubun liderini, alt süreç reaped edilmeden sabitler."""
    try:
        if (
            process.poll() is not None
            or os.getpgid(process.pid) != process.pid
            or os.getsid(process.pid) != process.pid
        ):
            raise AnchorOwnershipLost("ANCHOR_OWNERSHIP_LOST")
    except ProcessLookupError as error:
        raise AnchorOwnershipLost("ANCHOR_OWNERSHIP_LOST") from error
    return process.pid


def group_members(pgid: int) -> set[int]:
    """Yalnız önceden sabitlenmiş tek süreç grubunun sayısal üyelerini okur."""
    result = subprocess.run(  # noqa: S603 - sabit araç ve doğrulanmış sayısal PGID
        ["/usr/bin/pgrep", "-g", str(pgid)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
        text=True,
        timeout=2,
        check=False,
    )
    require(result.returncode in (0, 1), "GROUP_OBSERVATION_FAILED")
    values = result.stdout.split()
    require(
        all(value.isdecimal() and int(value) > 0 for value in values), "GROUP_OBSERVATION_FORMAT"
    )
    require(bool(values) == (result.returncode == 0), "GROUP_OBSERVATION_STATUS")
    return {int(value) for value in values}


def cleanup_anchor(
    process: subprocess.Popen[bytes],
    pgid: int | None,
    *,
    startup_confirmed: bool = False,
    grace_seconds: float = 10,
    kill_seconds: float = 5,
) -> dict[str, Any]:
    """Çıpayı canlı tutarak alt üyeleri bitirir; lider ve grup sonucunu ayırır."""
    result: dict[str, Any] = {
        "anchor_reaped": False,
        "group_status": "unverified",
        "group_authority": "spawn_pid_pgid_sid" if pgid is not None else "unverified",
        "term_sent": False,
        "kill_sent": False,
        "descendants_empty_before_anchor_reap": False,
        "startup_confirmed": startup_confirmed,
    }

    def signal_group(number: int) -> None:
        # poll canlı döndükten sonraki ölüm PID'yi yeniden kullandıramaz:
        # doğrudan çocuğu yalnız bu başlatıcı reaped eder; burada henüz etmez.
        if pgid is None or pin_anchor(process) != pgid:
            raise AnchorOwnershipLost("ANCHOR_OWNERSHIP_LOST")
        try:
            os.killpg(pgid, number)
        except ProcessLookupError as error:
            raise AnchorOwnershipLost("ANCHOR_OWNERSHIP_LOST") from error
        result["kill_sent" if number == signal.SIGKILL else "term_sent"] = True

    def wait_descendants(seconds: float, *, killed: bool) -> bool:
        deadline = time.monotonic() + seconds
        while True:
            if not killed:
                pin_anchor(process)
            # SIGKILL sonrasında burada poll/wait yok: ölü çıpanın PID'si
            # üyelik gözlemi tamamlanana kadar reaped edilmeden tutulur.
            members = group_members(pgid)
            if not killed and process.pid not in members:
                raise AnchorOwnershipLost("ANCHOR_NOT_IN_GROUP")
            if not members.difference({process.pid}):
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(min(0.05, max(0, deadline - time.monotonic())))

    try:
        if pgid is None:
            raise AnchorOwnershipLost("ANCHOR_NOT_PINNED")
        if not startup_confirmed:
            # Hazırlık el sıkışması yoksa çıpa henüz pytest oluşturabilir.
            # Boş grup gözlemiyle release vermek yerine oluşturmayı durdur.
            signal_group(signal.SIGKILL)
            empty = wait_descendants(kill_seconds, killed=True)
        else:
            empty = wait_descendants(0, killed=False)
            if not empty:
                signal_group(signal.SIGTERM)
                empty = wait_descendants(grace_seconds, killed=False)
        if not empty and not result["kill_sent"]:
            signal_group(signal.SIGKILL)
            empty = wait_descendants(kill_seconds, killed=True)
        result["descendants_empty_before_anchor_reap"] = empty
        result["group_status"] = "empty" if empty else "remaining_members"
        if not result["kill_sent"]:
            require(process.stdin is not None, "ANCHOR_CONTROL_MISSING")
            process.stdin.write(b"release\n")
            process.stdin.flush()
        result["anchor_exit_code"] = process.wait(timeout=5)
        result["anchor_reaped"] = True
        if not result["kill_sent"]:
            require(result["anchor_exit_code"] == 0, "ANCHOR_RELEASE_FAILED")
    except BaseException as error:
        result["group_status"] = "unverified"
        result["error"] = str(error) if isinstance(error, ProbeError) else "ANCHOR_CLEANUP_FAILED"
        # Kaybolmuş çıpanın PGID'sine yeniden dokunma. Diğer tanılama
        # hatalarında yalnız hâlâ sabitlenebilen canlı gruba bir kez KILL ver.
        if not isinstance(error, AnchorOwnershipLost) and not result["kill_sent"]:
            try:
                signal_group(signal.SIGKILL)
            except BaseException:
                result["kill_error"] = "ANCHOR_KILL_NOT_CONFIRMED"
        try:
            result["anchor_exit_code"] = process.wait(timeout=5)
            result["anchor_reaped"] = True
        except BaseException:
            result["reap_error"] = "ANCHOR_REAP_NOT_CONFIRMED"
    finally:
        if process.stdin is not None:
            try:
                process.stdin.close()
            except BaseException:
                result["control_close_error"] = "ANCHOR_CONTROL_CLOSE_FAILED"
    return result


def execute(private_config: Path) -> dict[str, Any]:
    record: dict[str, Any] = {"schema_version": 1, "status": "running", "run_id": uuid4().hex}
    process: subprocess.Popen[bytes] | None = None
    pgid: int | None = None
    read_descriptor: int | None = None
    write_descriptor: int | None = None
    try:
        # SIG_IGN otomatik reaping yapabilir; PID sabitleme için bunu reddet.
        require(signal.getsignal(signal.SIGCHLD) == signal.SIG_DFL, "ANCHOR_CHILD_REAP_POLICY")
        require(not (ROOT / "apps/api/.env").exists(), "ENV_FILE_NOT_ALLOWED")
        _, environment = private_settings(private_config)
        record["owned_new_database_verified"] = True
        record["source_before"] = source_hashes()
        raw_log = private_config.parent / f"d3-{record['run_id']}.private.log"
        junit = private_config.parent / f"d3-{record['run_id']}.private.xml"
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-c",
            str(ROOT / "apps/api/pyproject.toml"),
            "-q",
            "-p",
            "no:cacheprovider",
            "-p",
            "tests.conftest",
            str(ROOT / TEST),
            f"--junitxml={junit}",
        ]
        record["command"] = command
        read_descriptor, write_descriptor = os.pipe()
        anchor_command = [
            sys.executable,
            str(ROOT / ANCHOR),
            "--protocol-fd",
            str(write_descriptor),
            "--nonce",
            record["run_id"],
            "--",
            *command,
        ]
        record["anchor_command"] = anchor_command
        descriptor = os.open(raw_log, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        started = time.monotonic()
        with os.fdopen(descriptor, "wb") as stream:
            process = subprocess.Popen(  # noqa: S603 - sabit test hedefi; kabuk kullanılmaz
                anchor_command,
                cwd=ROOT / "apps/api",
                env=environment,
                stdin=subprocess.PIPE,
                stdout=stream,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                pass_fds=(write_descriptor,),
            )
            pgid = pin_anchor(process)
            os.close(write_descriptor)
            write_descriptor = None
            protocol = AnchorProtocol(read_descriptor)
            ready = protocol.read(timeout=10)
            require(
                ready
                == {
                    "event": "anchor-ready",
                    "nonce": record["run_id"],
                    "pid": process.pid,
                    "pgid": pgid,
                    "sid": pgid,
                    "pytest_started": True,
                },
                "ANCHOR_HANDSHAKE_FAILED",
            )
            record["anchor_handshake_verified"] = True
            exited = protocol.read(timeout=180)
            require(
                exited.get("event") == "pytest-exited" and type(exited.get("exit_code")) is int,
                "PYTEST_EXIT_PROTOCOL_FAILED",
            )
            returncode = exited["exit_code"]
        record["elapsed_seconds"] = round(time.monotonic() - started, 3)
        record["pytest_exit_code"] = returncode
        # Sabit pytest koşumuzun kullanıcıya ait 0700 izinli dizinde ürettiği XML.
        suites = ET.parse(junit).getroot()  # noqa: S314 - güvenilen yerel pytest XML çıktısı
        counts = {
            name: sum(int(suite.attrib.get(name, 0)) for suite in suites.iter("testsuite"))
            for name in ("tests", "failures", "errors", "skipped")
        }
        record["junit_counts"] = counts
        record["source_after"] = source_hashes()
        require(record["source_before"] == record["source_after"], "SOURCE_CHANGED")
        require(
            returncode == 0 and counts == {"tests": 2, "failures": 0, "errors": 0, "skipped": 0},
            "ACCEPTANCE_FAILED",
        )
        record["status"] = "passed"
    except BaseException as error:
        record["status"] = "failed"
        record["error"] = (
            str(error)
            if isinstance(error, ProbeError)
            else "D3_ACCEPTANCE_FAILED_REVIEW_PRIVATE_RECORD"
        )
    finally:
        if process is not None:
            record["cleanup"] = cleanup_anchor(
                process, pgid, startup_confirmed=record.get("anchor_handshake_verified", False)
            )
            cleanup = record["cleanup"]
            if (
                not cleanup["anchor_reaped"]
                or cleanup["group_status"] != "empty"
                or "error" in cleanup
                or "control_close_error" in cleanup
            ):
                record["status"] = "failed"
                record.setdefault("error", "OWNED_GROUP_CLEANUP_INCOMPLETE")
        for descriptor in (read_descriptor, write_descriptor):
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    record["protocol_close_error"] = "ANCHOR_PROTOCOL_CLOSE_FAILED"
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    # Çıktıyı veritabanına erişmeden ayır; mevcut kanıt dosyasının üzerine yazma.
    try:
        output = args.output.open("x", encoding="utf-8")
    except OSError:
        print('{"status":"failed","error":"OUTPUT_RESERVE_FAILED"}')
        return 1
    result = execute(args.private_config)
    encoded = json.dumps(result, indent=2) + "\n"
    try:
        with output:
            output.write(encoded)
    except OSError:
        result["output_error"] = "OUTPUT_WRITE_FAILED"
        print(json.dumps(result, indent=2))
        return 1
    print(encoded)
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
