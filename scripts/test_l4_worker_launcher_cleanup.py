"""D3 başlatıcısının sahiplik ve temizleme yarışlarını sahte süreçlerle sınar."""

from __future__ import annotations

import importlib.util
import io
import json
import signal
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

MODULE_PATH = Path(__file__).with_name("run_l4_worker_acceptance.py")
SPEC = importlib.util.spec_from_file_location("d3_launcher_candidate", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
launcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launcher)
ANCHOR_SPEC = importlib.util.spec_from_file_location(
    "d3_anchor_candidate", MODULE_PATH.with_name("l4_worker_group_anchor.py")
)
assert ANCHOR_SPEC is not None and ANCHOR_SPEC.loader is not None
anchor = importlib.util.module_from_spec(ANCHOR_SPEC)
ANCHOR_SPEC.loader.exec_module(anchor)


class FakeProcess:
    """Anchor canlılığını, pytest/worker üyelerinden ayrı tutar."""

    pid = 42420

    def __init__(self) -> None:
        self.stdin = io.BytesIO()
        self.returncode: int | None = None
        self.killed = False
        self.polls_after_kill = 0

    def poll(self) -> int | None:
        if self.killed:
            self.polls_after_kill += 1
        return self.returncode

    def wait(self, timeout: float) -> int:
        if self.returncode is None:
            self.returncode = -signal.SIGKILL if self.killed else 0
        return self.returncode


class CleanupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.process = FakeProcess()
        self.clock = 0.0
        self.members = {self.process.pid}
        self.signals: list[tuple[int, int]] = []
        self.term_removes_children = False
        self.kill_removes_children = True
        self.patches = [
            patch.object(launcher.time, "monotonic", side_effect=lambda: self.clock),
            patch.object(launcher.time, "sleep", side_effect=self.sleep),
            patch.object(launcher.os, "getpgid", return_value=self.process.pid),
            patch.object(launcher.os, "getsid", return_value=self.process.pid),
            patch.object(launcher.os, "killpg", side_effect=self.killpg),
            patch.object(launcher, "group_members", side_effect=lambda _pgid: set(self.members)),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def sleep(self, seconds: float) -> None:
        self.clock += seconds

    def killpg(self, pgid: int, number: int) -> None:
        self.signals.append((pgid, number))
        if number == signal.SIGTERM and self.term_removes_children:
            self.members = {self.process.pid}
        if number == signal.SIGKILL:
            self.process.killed = True
            if self.kill_removes_children:
                self.members = {self.process.pid}

    def cleanup(self) -> dict:
        return launcher.cleanup_anchor(
            self.process,
            self.process.pid,
            startup_confirmed=True,
            grace_seconds=0.2,
            kill_seconds=0.2,
        )

    def test_finished_pytest_with_remaining_worker_escalates_before_anchor_reap(self) -> None:
        # Pytest bitmiş olsa da kalan worker aynı grubun bağımsız bir üyesidir.
        self.members.add(self.process.pid + 1)
        result = self.cleanup()
        self.assertEqual(
            self.signals,
            [(self.process.pid, signal.SIGTERM), (self.process.pid, signal.SIGKILL)],
        )
        self.assertEqual(result["group_status"], "empty")
        self.assertTrue(result["anchor_reaped"])
        self.assertTrue(result["descendants_empty_before_anchor_reap"])
        self.assertEqual(self.process.polls_after_kill, 0)
        self.assertLessEqual(self.clock, 0.4)

    def test_graceful_descendant_exit_releases_anchor_without_kill(self) -> None:
        self.members.add(self.process.pid + 1)
        self.term_removes_children = True
        result = self.cleanup()
        self.assertEqual(self.signals, [(self.process.pid, signal.SIGTERM)])
        self.assertTrue(result["anchor_reaped"])
        self.assertFalse(result["kill_sent"])
        self.assertEqual(result["group_status"], "empty")

    def test_empty_group_releases_anchor_without_any_signal(self) -> None:
        result = self.cleanup()
        self.assertEqual(self.signals, [])
        self.assertEqual(result["group_status"], "empty")
        self.assertTrue(result["anchor_reaped"])

    def test_dead_anchor_never_signals_even_if_numeric_group_is_reused(self) -> None:
        self.process.returncode = 1
        self.members.add(self.process.pid + 99)
        result = self.cleanup()
        self.assertEqual(self.signals, [])
        self.assertEqual(result["group_status"], "unverified")
        self.assertEqual(result["error"], "ANCHOR_OWNERSHIP_LOST")
        self.assertTrue(result["anchor_reaped"])
        self.assertFalse(result["descendants_empty_before_anchor_reap"])

    def test_lookup_race_stops_all_group_signals(self) -> None:
        with patch.object(launcher.os, "getpgid", side_effect=ProcessLookupError):
            result = self.cleanup()
        self.assertEqual(self.signals, [])
        self.assertEqual(result["error"], "ANCHOR_OWNERSHIP_LOST")

    def test_term_race_does_not_retry_on_another_group(self) -> None:
        self.members.add(self.process.pid + 1)
        with patch.object(launcher.os, "killpg", side_effect=ProcessLookupError) as send:
            result = self.cleanup()
        self.assertEqual(send.call_count, 1)
        self.assertEqual(result["error"], "ANCHOR_OWNERSHIP_LOST")
        self.assertFalse(result["kill_sent"])

    def test_kill_race_is_a_recorded_failure_without_second_kill(self) -> None:
        self.members.add(self.process.pid + 1)
        with patch.object(launcher.os, "killpg", side_effect=[None, ProcessLookupError]) as send:
            result = self.cleanup()
        self.assertEqual(send.call_count, 2)
        self.assertEqual(result["error"], "ANCHOR_OWNERSHIP_LOST")
        self.assertFalse(result["kill_sent"])

    def test_remaining_member_is_not_reported_as_reaped_group(self) -> None:
        self.members.add(self.process.pid + 1)
        self.kill_removes_children = False
        result = self.cleanup()
        self.assertTrue(result["anchor_reaped"])
        self.assertEqual(result["group_status"], "remaining_members")
        self.assertFalse(result["descendants_empty_before_anchor_reap"])
        self.assertEqual(len(self.signals), 2)

    def test_observation_failure_kills_only_live_anchor_group_and_fails_closed(self) -> None:
        with patch.object(launcher, "group_members", side_effect=OSError):
            result = self.cleanup()
        self.assertEqual(self.signals, [(self.process.pid, signal.SIGKILL)])
        self.assertEqual(result["group_status"], "unverified")
        self.assertEqual(result["error"], "ANCHOR_CLEANUP_FAILED")

    def test_reserved_json_survives_timeout_and_cleanup_lookup_race(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "apps/api").mkdir(parents=True)
            config = root / "private.json"
            output = root / "result.json"
            settings = ({}, {"DOU_L4_D3_PREFLIGHT": "owned-new-database-verified"})
            events = Mock()
            events.read.side_effect = launcher.ProbeError("ANCHOR_PROTOCOL_TIMEOUT")
            with (
                patch.object(launcher, "ROOT", root),
                patch.object(launcher, "private_settings", return_value=settings),
                patch.object(launcher, "source_hashes", return_value={"synthetic.py": "fixed"}),
                patch.object(launcher.subprocess, "Popen", return_value=self.process),
                patch.object(launcher, "AnchorProtocol", return_value=events),
                patch.object(
                    launcher.os, "getpgid", side_effect=[self.process.pid, ProcessLookupError]
                ),
                patch.object(
                    launcher.sys,
                    "argv",
                    ["probe", "--private-config", str(config), "--output", str(output)],
                ),
                patch("builtins.print"),
            ):
                exit_code = launcher.main()
            result = json.loads(output.read_text())
            self.assertEqual(exit_code, 1)
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["error"], "ANCHOR_PROTOCOL_TIMEOUT")
            self.assertEqual(result["cleanup"]["error"], "ANCHOR_OWNERSHIP_LOST")
            self.assertEqual(self.signals, [])

    def test_automatic_reaping_is_rejected_before_private_settings_or_spawn(self) -> None:
        with (
            patch.object(launcher.signal, "getsignal", return_value=signal.SIG_IGN),
            patch.object(launcher, "private_settings") as settings,
            patch.object(launcher.subprocess, "Popen") as spawn,
        ):
            result = launcher.execute(Path("unused-private-config"))
        self.assertEqual(result["error"], "ANCHOR_CHILD_REAP_POLICY")
        settings.assert_not_called()
        spawn.assert_not_called()

    def test_startup_timeout_never_releases_anchor_that_could_spawn_later(self) -> None:
        result = launcher.cleanup_anchor(
            self.process, self.process.pid, startup_confirmed=False, kill_seconds=0.2
        )
        self.assertEqual(self.signals, [(self.process.pid, signal.SIGKILL)])
        self.assertEqual(result["group_status"], "empty")
        self.assertFalse(result["startup_confirmed"])
        self.assertEqual(self.process.polls_after_kill, 0)

    def test_startup_timeout_with_remaining_member_never_kills_twice(self) -> None:
        self.members.add(self.process.pid + 1)
        self.kill_removes_children = False
        result = launcher.cleanup_anchor(
            self.process, self.process.pid, startup_confirmed=False, kill_seconds=0.2
        )
        self.assertEqual(self.signals, [(self.process.pid, signal.SIGKILL)])
        self.assertEqual(result["group_status"], "remaining_members")
        self.assertEqual(self.process.polls_after_kill, 0)


class AnchorTests(unittest.TestCase):
    def test_group_observation_is_restricted_to_one_pinned_group(self) -> None:
        completed = SimpleNamespace(returncode=0, stdout="42420\n42421\n")
        with patch.object(launcher.subprocess, "run", return_value=completed) as run:
            self.assertEqual(launcher.group_members(42420), {42420, 42421})
        self.assertEqual(run.call_args.args[0], ["/usr/bin/pgrep", "-g", "42420"])
        self.assertEqual(run.call_args.kwargs["timeout"], 2)

    def run_anchor(self, control: bytes) -> tuple[int, Mock, Mock, Mock]:
        arguments = SimpleNamespace(
            protocol_fd=55,
            nonce="synthetic-nonce",
            command=["--", anchor.sys.executable, "-m", "pytest", "synthetic-test.py"],
        )
        child = Mock()
        child.poll.return_value = 0
        protocol = io.StringIO()
        with (
            patch.object(anchor.argparse.ArgumentParser, "parse_args", return_value=arguments),
            patch.object(anchor.os, "getpid", return_value=42420),
            patch.object(anchor.os, "getpgrp", return_value=42420),
            patch.object(anchor.os, "getsid", return_value=42420),
            patch.dict(anchor.os.environ, {"DOU_L4_D3_PREFLIGHT": "owned-new-database-verified"}),
            patch.object(anchor.os, "fdopen", return_value=protocol),
            patch.object(anchor.os, "read", return_value=control),
            patch.object(anchor.sys, "stdin", Mock(fileno=Mock(return_value=56))),
            patch.object(anchor.select, "select", return_value=([56], [], [])),
            patch.object(anchor.signal, "signal") as install,
            patch.object(anchor.subprocess, "Popen", return_value=child) as spawn,
            patch.object(anchor.os, "killpg") as send,
            patch.object(anchor.time, "sleep") as sleep,
        ):
            exit_code = anchor.main()
        for number in (signal.SIGTERM, signal.SIGINT):
            self.assertIn(unittest.mock.call(number, anchor.retain_anchor), install.call_args_list)
        self.assertFalse(spawn.call_args.kwargs["start_new_session"])
        return exit_code, spawn, send, sleep

    def test_anchor_releases_only_after_child_exit_without_ignoring_child_signals(self) -> None:
        exit_code, _spawn, send, sleep = self.run_anchor(b"release\n")
        self.assertEqual(exit_code, 0)
        send.assert_not_called()
        sleep.assert_not_called()

    def test_disconnected_launcher_closes_only_anchors_own_group_with_bounded_grace(self) -> None:
        exit_code, _spawn, send, sleep = self.run_anchor(b"")
        self.assertEqual(exit_code, 3)
        self.assertEqual(
            send.call_args_list,
            [unittest.mock.call(42420, signal.SIGTERM), unittest.mock.call(42420, signal.SIGKILL)],
        )
        sleep.assert_called_once_with(10)


if __name__ == "__main__":
    unittest.main()
