"""Own the synthetic E2E API lifecycle and account for every remaining audit row.

The caller provisions and pins an exclusive synthetic database first. This tool
does not discover ownership, change database privileges, or delete audit rows.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import select
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener

import e2e_audit_guard as guard


def source_hashes(repo: Path) -> dict[str, str]:
    paths: set[Path] = set()
    for directory, suffixes in {
        "apps/api/app": {".py"},
        "apps/web/app": {".ts", ".tsx", ".css"},
        "apps/web/components": {".ts", ".tsx", ".css"},
        "apps/web/lib": {".ts", ".tsx"},
        "apps/web/e2e": {".ts"},
        "supabase/migrations": {".sql"},
        "scripts": {".py"},
    }.items():
        paths.update(p for p in (repo / directory).rglob("*") if p.suffix in suffixes)
    paths.update(
        repo / p
        for p in (
            "apps/web/playwright.config.ts",
            "apps/web/package.json",
            "docs/kvkk.md",
            "apps/web/next.config.ts",
            "apps/web/tsconfig.json",
            ".github/workflows/ci.yml",
            "supabase/seed_demo.sql",
            "supabase/local_dev_setup.sql",
        )
    )
    return {
        str(p.relative_to(repo)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)
    }


def child_environment(repo: Path, pins: dict, output: Path, web_port: int) -> dict[str, str]:
    # No ambient provider secrets, PG routing, .env file, or app configuration.
    env = {k: os.environ[k] for k in ("PATH", "LANG", "TZ", "SYSTEMROOT") if k in os.environ}
    address = f"127.0.0.1:{pins['port']}/{pins['databaseName']}"
    env.update(
        {
            "PYTHONPATH": str(repo / "apps/api"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "ENVIRONMENT": "local",
            "DEV_AUTH_ENABLED": "true",
            "DATABASE_URL": f"postgresql+psycopg://dou_app:dou_app_local@{address}",
            "WORKER_DATABASE_URL": f"postgresql+psycopg://dou_worker:dou_worker_local@{address}",
            "CORS_ORIGINS": json.dumps([f"http://localhost:{web_port}"]),
            "QUESTION_AUTHORING_ENABLED": "true",
            "STUDENT_ASSESSMENT_WORKSPACE_ENABLED": "true",
            "EMBEDDING_PROVIDER": "hashing",
            "LLM_FAKE_PROVIDER": "true",
            "EVAL_RUNTIME_ENABLED": "false",
            "GROQ_API_KEY": "",
            "GEMINI_API_KEY": "",
            "OPENAI_API_KEY": "",
            "STORAGE_BACKEND": "local",
            "STORAGE_ROOT": str(output / "storage"),
        }
    )
    return env


def serve_owned(fd: int) -> int:
    """A private parent pipe requests graceful Uvicorn shutdown, then real wait.

    EOF also shuts down if the controller disappears. No test route, timer, or
    application monkeypatch is installed. Signals remain Uvicorn's fallback.
    """
    import uvicorn

    listener = socket.socket(fileno=fd)
    server = uvicorn.Server(uvicorn.Config("app.main:app", log_level="info", lifespan="on"))
    control_received = False
    finished = threading.Event()

    def control() -> None:
        nonlocal control_received
        # A daemon blocked on BufferedReader.readline can abort Python during
        # startup failure. Raw pipe reads and a bounded join release the reader.
        while not finished.is_set():
            try:
                readable, _, _ = select.select([sys.stdin.fileno()], [], [], 0.1)
                if not readable:
                    continue
                control_received = os.read(sys.stdin.fileno(), 16) == b"stop\n"
            except OSError:
                control_received = False
            server.should_exit = True
            return

    reader = threading.Thread(target=control, daemon=True, name="owned-e2e-control")
    reader.start()
    try:
        server.run(sockets=[listener])
    finally:
        finished.set()
        reader.join(timeout=1)
        listener.close()
    lifecycle = server.lifespan
    clean = (
        not reader.is_alive()
        and server.started
        and control_received
        and lifecycle.startup_event.is_set()
        and lifecycle.shutdown_event.is_set()
        and not lifecycle.startup_failed
        and not lifecycle.shutdown_failed
        and not lifecycle.error_occurred
    )
    return 0 if clean else 1


def stop_owned_api(process: subprocess.Popen, timeout: float = 30) -> tuple[int, str]:
    if process.poll() is not None:
        return process.wait(), "exited-before-stop"
    stop_kind = "graceful-pipe-and-wait"
    try:
        process.stdin.write(b"stop\n")
        process.stdin.flush()
        process.stdin.close()
    except (BrokenPipeError, OSError):
        stop_kind = "control-pipe-failed"
    try:
        return process.wait(timeout=timeout), stop_kind
    except subprocess.TimeoutExpired:
        process.terminate()
        try:
            return process.wait(timeout=10), "forced-terminate"
        except subprocess.TimeoutExpired:
            process.kill()
            return process.wait(timeout=10), "forced-kill"


def wait_ready(process: subprocess.Popen, origin: str, timeout: float = 40) -> None:
    opener = build_opener(ProxyHandler({}))
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        guard.require(process.poll() is None, "OWNED_API_EXITED_BEFORE_READY")
        try:
            with opener.open(Request(origin + "/health/ready"), timeout=1) as response:  # noqa: S310 — pinned numeric HTTP origin.
                if response.status == 200:
                    return
        except (OSError, ValueError):
            pass
        time.sleep(0.1)
    raise guard.GuardError("OWNED_API_NOT_READY")


def run(args: argparse.Namespace) -> int:
    repo = args.repo.resolve(strict=True)
    guard.require(
        Path(__file__).resolve() == repo / "scripts/run_owned_e2e.py"
        and Path(guard.__file__).resolve() == repo / "scripts/e2e_audit_guard.py",
        "EXECUTED_CONTROLLER_SOURCE_MISMATCH",
    )
    pins = guard.read_pins(args.pins, args.pins_sha256)
    if pins["issuer"] == "github-owned-service":
        guard.require(
            os.environ.get("GITHUB_ACTIONS") == "true" and os.environ.get("CI") == "true",
            "GITHUB_JOB_CONTEXT_REQUIRED",
        )
    guard.require(0 < args.web_port < 65536, "WEB_PORT")
    output = args.output
    guard.require(output.is_absolute() and output.resolve() == output, "OUTPUT_PATH")
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    (output / "api-cwd").mkdir(mode=0o700)
    before = source_hashes(repo)
    guard.private_write(output / "source-before.json", before)
    audit_directory = output / "audit"
    guard_command = [
        sys.executable,
        str(Path(__file__).with_name("e2e_audit_guard.py")),
        "--pins",
        str(args.pins),
        "--pins-sha256",
        args.pins_sha256,
        "--passfile",
        str(args.passfile),
        "--directory",
        str(audit_directory),
        "--run-id",
        args.run_id,
        "--execute",
    ]
    begin = subprocess.run([*guard_command, "--phase", "begin"], capture_output=True, check=False)  # noqa: S603 — fixed colocated guard, validated pins.
    (output / "guard-begin.log").write_bytes(begin.stdout + begin.stderr)
    guard.require(begin.returncode == 0, "AUDIT_BEGIN_FAILED")
    capture_env = json.loads(guard.private_read(audit_directory / "environment.json"))
    guard.require(
        set(capture_env)
        == {
            "E2E_RUN_ID",
            "E2E_DATABASE_NAME",
            "E2E_API_URL",
            "E2E_AUDIT_TARGET_ID",
            "E2E_AUDIT_DIR",
        },
        "AUDIT_ENV_SCHEMA",
    )
    api_env = child_environment(repo, pins, output, args.web_port)
    # The browser requires the user's runtime/browser paths, but inherits no
    # database route or application secrets. The private passfile is explicit.
    web_env = {
        k: os.environ[k]
        for k in (
            "PATH",
            "HOME",
            "LANG",
            "TZ",
            "CI",
            "PG_BIN",
            "NODE_EXTRA_CA_CERTS",
            "NODE_OPTIONS",
            "PLAYWRIGHT_BROWSERS_PATH",
        )
        if k in os.environ
    }
    web_env.update(capture_env)
    if pins["issuer"] == "github-owned-service":
        web_env["GITHUB_ACTIONS"] = "true"
    web_env.update(
        PGHOST="127.0.0.1",
        PGHOSTADDR="127.0.0.1",
        PGPORT=str(pins["port"]),
        PGUSER=pins["dbaRole"],
        PGPASSFILE=str(args.passfile),
        E2E_PORT=str(args.web_port),
        E2E_WEBPACK_BUILD="1" if args.webpack else "0",
        NEXT_TELEMETRY_DISABLED="1",
        # API tarafı (child_environment) DEV_AUTH_ENABLED=true ile kalkıyor; web
        # L5'ten beri giriş ekranını bu bayrakla kapılıyor. Bayrak taşınmayınca
        # ekran "Oturum açma henüz yapılandırılmadı" diyor ve giriş bekleyen her
        # test zaman aşımına düşüyor (OWNED_E2E_FAILED, 14 Eylül 2026). Yalnız bu
        # izole sentetik hedefte açılır; üretim kapısı değişmez.
        NEXT_PUBLIC_DEV_AUTH="true",
        NEXT_PUBLIC_SUPABASE_URL="",
        NEXT_PUBLIC_SUPABASE_ANON_KEY="",
        GROQ_API_KEY="",
        GEMINI_API_KEY="",
        OPENAI_API_KEY="",
    )
    started = time.monotonic()
    playwright_code = 1
    api_code = None
    stop_kind = "not-started"
    error_code = None
    api = None
    browser = None
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # Bind before launch and pass the actual listening socket. A different
        # service cannot satisfy readiness by occupying the configured port.
        listener.bind(("127.0.0.1", urlsplit(pins["apiOrigin"]).port))
        listener.listen(128)
        with (
            (output / "api.log").open("xb") as api_log,
            (output / "playwright.log").open("xb") as web_log,
        ):
            api = subprocess.Popen(  # noqa: S603 — current interpreter and verified controller.
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--serve-owned",
                    str(listener.fileno()),
                ],
                env=api_env,
                cwd=output / "api-cwd",
                pass_fds=(listener.fileno(),),
                stdin=subprocess.PIPE,
                stdout=api_log,
                stderr=subprocess.STDOUT,
            )
            listener.close()
            try:
                wait_ready(api, pins["apiOrigin"])
                browser = subprocess.Popen(
                    ["bun", "run", "test:e2e", "--workers=1"],  # noqa: S607 — CI-provisioned Bun on explicit runtime PATH.
                    cwd=repo / "apps/web",
                    env=web_env,
                    stdin=subprocess.DEVNULL,
                    stdout=web_log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
                playwright_code = browser.wait(timeout=args.test_timeout)
            finally:
                try:
                    if browser is not None and browser.poll() is None:
                        # Only the process group created above belongs to this run.
                        os.killpg(browser.pid, signal.SIGTERM)
                        try:
                            browser.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            os.killpg(browser.pid, signal.SIGKILL)
                            browser.wait(timeout=10)
                finally:
                    api_code, stop_kind = stop_owned_api(api)
    except guard.GuardError as error:
        error_code = str(error)
    except Exception:
        error_code = "OWNED_E2E_FAILED"
    finally:
        listener.close()
    finish_code = None
    if api is not None and api_code == 0 and stop_kind == "graceful-pipe-and-wait":
        quiescence = {
            "version": 1,
            "runId": args.run_id,
            "targetId": capture_env["E2E_AUDIT_TARGET_ID"],
            "ownedApiPid": api.pid,
            "ownedApiExitCode": api_code,
            "playwrightExitCode": playwright_code,
            "state": "stopped",
        }
        path = output / "quiescence.json"
        guard.private_write(path, quiescence)
        finish = subprocess.run(  # noqa: S603 — fixed colocated guard, validated pins.
            [*guard_command, "--phase", "finish", "--quiescence-receipt", str(path)],
            capture_output=True,
            check=False,
        )
        finish_code = finish.returncode
        (output / "guard-finish.log").write_bytes(finish.stdout + finish.stderr)
    after = source_hashes(repo)
    guard.private_write(output / "source-after.json", after)
    success = (
        error_code is None
        and playwright_code == 0
        and api_code == 0
        and stop_kind == "graceful-pipe-and-wait"
        and finish_code == 0
        and before == after
    )
    result = {
        "status": "PASS" if success else "FAIL",
        "runId": args.run_id,
        "targetId": capture_env["E2E_AUDIT_TARGET_ID"],
        "playwrightExitCode": playwright_code,
        "ownedApiPid": None if api is None else api.pid,
        "ownedApiExitCode": api_code,
        "stopObservation": stop_kind,
        "auditFinishExitCode": finish_code,
        "errorCode": error_code,
        "sourceUnchanged": before == after,
        "webBuild": "webpack" if args.webpack else "default",
        "seconds": round(time.monotonic() - started, 3),
        "scope": (
            "Synthetic local auth, hashing embeddings, fake model; no hosted or real-provider claim"
        ),
    }
    guard.private_write(output / "result.json", result)
    print(json.dumps(result))
    return 0 if success else 1


def main() -> int:
    if len(sys.argv) == 3 and sys.argv[1] == "--serve-owned":
        return serve_owned(int(sys.argv[2]))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--pins", type=Path, required=True)
    parser.add_argument("--pins-sha256", required=True)
    parser.add_argument("--passfile", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--web-port", type=int, default=3100)
    parser.add_argument("--webpack", action="store_true")
    parser.add_argument("--test-timeout", type=float, default=900)
    args = parser.parse_args()
    os.umask(0o077)
    try:
        return run(args)
    except guard.GuardError as error:
        print(json.dumps({"status": "FAIL", "code": str(error)}))
        return 2
    except Exception:
        print(json.dumps({"status": "FAIL", "code": "OWNED_E2E_FAILED"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
