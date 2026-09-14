"""D3 test grubunu temizleme bitene kadar canlı tutan özel süreç çıpası."""

from __future__ import annotations

import argparse
import json
import os
import select
import signal
import subprocess
import sys
import time
from typing import Any


def retain_anchor(_signum: int, _frame: object) -> None:
    """SIGTERM gruptaki testleri durdururken çıpanın sahipliğini korur."""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol-fd", required=True, type=int)
    parser.add_argument("--nonce", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if (
        os.getpid() != os.getpgrp()
        or os.getsid(0) != os.getpid()
        or command[:3] != [sys.executable, "-m", "pytest"]
        or os.environ.get("DOU_L4_D3_PREFLIGHT") != "owned-new-database-verified"
    ):
        return 2

    # SIG_IGN exec ile miras kalır; Python işleyicisi pytest exec'inde sıfırlanır.
    signal.signal(signal.SIGTERM, retain_anchor)
    signal.signal(signal.SIGINT, retain_anchor)
    protocol = os.fdopen(args.protocol_fd, "w", buffering=1)

    def emit(value: dict[str, Any]) -> None:
        try:
            protocol.write(json.dumps(value) + "\n")
        except (BrokenPipeError, OSError):
            # Başlatıcı sonuç borusunu kapatsa da temizleme borusunu dinle.
            pass

    child: subprocess.Popen[bytes] | None = None
    try:
        child = subprocess.Popen(  # noqa: S603 - başlatıcının sabit pytest komutu
            command,
            stdin=subprocess.DEVNULL,
            start_new_session=False,
        )
    except OSError:
        pass
    emit(
        {
            "event": "anchor-ready",
            "nonce": args.nonce,
            "pid": os.getpid(),
            "pgid": os.getpgrp(),
            "sid": os.getsid(0),
            "pytest_started": child is not None,
        }
    )
    reported = False
    control = bytearray()
    while True:
        if child is not None and not reported:
            exit_code = child.poll()
            if exit_code is not None:
                emit({"event": "pytest-exited", "exit_code": exit_code})
                reported = True
        readable, _, _ = select.select([sys.stdin.fileno()], [], [], 0.05)
        if not readable:
            continue
        data = os.read(sys.stdin.fileno(), 128)
        if not data:
            # Başlatıcı kaybolursa kendi hâlâ canlı grubumuzu sınırlı sürede kapat.
            os.killpg(os.getpgrp(), signal.SIGTERM)
            time.sleep(10)
            os.killpg(os.getpgrp(), signal.SIGKILL)
            return 3
        control.extend(data)
        if len(control) > 128:
            return 4
        if b"\n" not in control:
            continue
        if control == b"release\n" and (child is None or child.poll() is not None):
            protocol.close()
            return 0
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
