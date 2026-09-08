"""Owned E2E lifecycle: offline stop contracts and three isolated ASGI children.

No product app, database, model or remote service is used by these tests.
"""

from __future__ import annotations

import http.client
import importlib.util
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


def load_controller():
    source = Path(__file__).resolve().with_name("run_owned_e2e.py")
    guard = source.with_name("e2e_audit_guard.py")
    for name, path in (("e2e_audit_guard", guard), ("owned_controller_under_test", source)):
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise RuntimeError("CONTROLLER_IMPORT_SPEC")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules["owned_controller_under_test"]


class FakePipe:
    def __init__(self, owner, failed_stage):
        self.owner = owner
        self.failed_stage = failed_stage

    def operation(self, stage):
        self.owner.calls.append(stage)
        if stage == self.failed_stage:
            raise OSError("synthetic-control-pipe-failure")

    def write(self, value):
        if value != b"stop\n":
            raise AssertionError("wrong control bytes")
        self.operation("write")

    def flush(self):
        self.operation("flush")

    def close(self):
        self.operation("close")


class FakeProcess:
    def __init__(self, waits, failed_stage=None, already_exited=None):
        self.calls = []
        self.waits = list(waits)
        self.returncode = already_exited
        self.stdin = FakePipe(self, failed_stage)
        self.started_live = already_exited is None

    def poll(self):
        self.calls.append("poll")
        return self.returncode

    def wait(self, timeout=None):
        self.calls.append(("wait", timeout))
        if self.started_live and timeout is None:
            raise AssertionError("an initially live child must never have an unbounded wait")
        if not self.waits:
            raise AssertionError("unexpected additional wait")
        value = self.waits.pop(0)
        if value == "timeout":
            raise subprocess.TimeoutExpired("synthetic-owned-child", timeout)
        self.returncode = value
        return value

    def terminate(self):
        self.calls.append("terminate")

    def kill(self):
        self.calls.append("kill")


class StopOwnedContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.controller = load_controller()

    def test_normal_pipe_and_observed_exit(self):
        process = FakeProcess([0])
        self.assertEqual(
            self.controller.stop_owned_api(process, 0.1), (0, "graceful-pipe-and-wait")
        )
        self.assertEqual(process.calls, ["poll", "write", "flush", "close", ("wait", 0.1)])

    def test_write_failure_timeout_still_terminates_and_reaps(self):
        process = FakeProcess(["timeout", 0], failed_stage="write")
        self.assertEqual(self.controller.stop_owned_api(process, 0.1), (0, "forced-terminate"))
        self.assertEqual(process.calls, ["poll", "write", ("wait", 0.1), "terminate", ("wait", 10)])
        self.assertEqual(process.returncode, 0)

    def test_flush_failure_two_timeouts_still_kills_and_reaps(self):
        process = FakeProcess(["timeout", "timeout", -9], failed_stage="flush")
        self.assertEqual(self.controller.stop_owned_api(process, 0.1), (-9, "forced-kill"))
        self.assertEqual(
            process.calls,
            [
                "poll",
                "write",
                "flush",
                ("wait", 0.1),
                "terminate",
                ("wait", 10),
                "kill",
                ("wait", 10),
            ],
        )
        self.assertEqual(process.returncode, -9)

    def test_failed_write_then_exit0_is_never_clean(self):
        process = FakeProcess([0], failed_stage="write")
        self.assertEqual(self.controller.stop_owned_api(process, 0.1), (0, "control-pipe-failed"))
        self.assertNotIn("terminate", process.calls)

    def test_failed_close_then_exit0_is_never_clean(self):
        process = FakeProcess([0], failed_stage="close")
        self.assertEqual(self.controller.stop_owned_api(process, 0.1), (0, "control-pipe-failed"))

    def test_timeout_after_normal_write_preserves_actual_signal_exit(self):
        process = FakeProcess(["timeout", -15])
        self.assertEqual(self.controller.stop_owned_api(process, 0.1), (-15, "forced-terminate"))
        self.assertEqual(process.returncode, -15)

    def test_already_exited_child_is_not_claimed_as_normal_stop(self):
        process = FakeProcess([7], already_exited=7)
        self.assertEqual(self.controller.stop_owned_api(process, 0.1), (7, "exited-before-stop"))
        self.assertEqual(process.calls, ["poll", ("wait", None)])

    def test_unreapable_child_cannot_produce_success(self):
        process = FakeProcess(["timeout", "timeout", "timeout"], failed_stage="write")
        with self.assertRaises(subprocess.TimeoutExpired):
            self.controller.stop_owned_api(process, 0.1)
        self.assertIn("terminate", process.calls)
        self.assertIn("kill", process.calls)
        self.assertIsNone(process.returncode)
        self.assertFalse(process.waits)


FIXTURE_SOURCE = '"""Private synthetic ASGI lifecycle fixture; no DB or provider code."""\nimport os\n\nCASE = os.environ["OWNED_LIFECYCLE_CASE"]\n\nasync def app(scope, receive, send):\n    if scope["type"] == "lifespan":\n        while True:\n            message = await receive()\n            if message["type"] == "lifespan.startup":\n                if CASE == "startup-failed":\n                    await send({"type": "lifespan.startup.failed", "message": "synthetic startup failure"})\n                    return\n                await send({"type": "lifespan.startup.complete"})\n            elif message["type"] == "lifespan.shutdown":\n                if CASE == "shutdown-failed":\n                    await send({"type": "lifespan.shutdown.failed", "message": "synthetic shutdown failure"})\n                else:\n                    await send({"type": "lifespan.shutdown.complete"})\n                return\n    elif scope["type"] == "http":\n        while True:\n            message = await receive()\n            if message["type"] == "http.disconnect":\n                return\n            if message["type"] == "http.request" and not message.get("more_body", False):\n                break\n        body = b\'{"status":"ready","fixture":true}\'\n        status = 200 if scope["path"] == "/health/ready" else 404\n        await send({"type": "http.response.start", "status": status,\n                    "headers": [(b"content-type", b"application/json"),\n                                (b"content-length", str(len(body)).encode("ascii"))]})\n        await send({"type": "http.response.body", "body": body})\n'  # noqa: E501 — byte-exact synthetic fixture shared with measured probe.


class RealOwnedLifecycle(unittest.TestCase):
    def observe(self, case, expected):
        with tempfile.TemporaryDirectory(prefix="dou-owned-lifecycle-") as temporary:
            root = Path(temporary).resolve()
            package = root / "app"
            package.mkdir()
            (package / "__init__.py").write_text("")
            (package / "main.py").write_text(FIXTURE_SOURCE)
            env = {key: os.environ[key] for key in ("PATH", "LANG", "TZ") if key in os.environ}
            env.update(PYTHONPATH=str(root), PYTHONDONTWRITEBYTECODE="1", OWNED_LIFECYCLE_CASE=case)
            listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            child = None
            forced = False
            try:
                listener.bind(("127.0.0.1", 0))
                listener.listen(128)
                port = listener.getsockname()[1]
                with (root / "child.log").open("xb") as log:
                    child = subprocess.Popen(  # noqa: S603 — test-owned interpreter, controller and socket.
                        [
                            sys.executable,
                            str(Path(__file__).resolve().with_name("run_owned_e2e.py")),
                            "--serve-owned",
                            str(listener.fileno()),
                        ],
                        env=env,
                        cwd=root,
                        pass_fds=(listener.fileno(),),
                        stdin=subprocess.PIPE,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                    )
                    listener.close()
                    if case != "startup-failed":
                        ready = False
                        deadline = time.monotonic() + 10
                        while time.monotonic() < deadline:
                            self.assertIsNone(child.poll(), "child exited before readiness")
                            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=0.2)
                            try:
                                connection.request("GET", "/health/ready")
                                response = connection.getresponse()
                                body = response.read()
                                self.assertEqual(response.status, 200)
                                self.assertEqual(body, b'{"status":"ready","fixture":true}')
                                ready = True
                                break
                            except (OSError, http.client.HTTPException):
                                time.sleep(0.025)
                            finally:
                                connection.close()
                        self.assertTrue(ready, "owned fixture never became ready")
                        child.stdin.write(b"stop\n")
                        child.stdin.flush()
                        child.stdin.close()
                    self.assertEqual(child.wait(timeout=10), expected)
                self.assertNotIn(b"Fatal Python error", (root / "child.log").read_bytes())
            finally:
                listener.close()
                if child is not None:
                    if child.poll() is None:
                        forced = True
                        child.terminate()
                        try:
                            child.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            child.kill()
                            child.wait(timeout=2)
                    if not child.stdin.closed:
                        child.stdin.close()
                self.assertFalse(forced, "test needed forced child cleanup")

    def test_normal_lifecycle_exits_zero(self):
        self.observe("normal", 0)

    def test_startup_failure_preserves_uvicorn_exit_without_python_abort(self):
        self.observe("startup-failed", 3)

    def test_shutdown_failure_cannot_report_success(self):
        self.observe("shutdown-failed", 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
