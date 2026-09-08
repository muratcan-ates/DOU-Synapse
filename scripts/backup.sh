#!/bin/sh
set -eu
exec "${DOU_RECOVERY_PYTHON:-python3}" "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)/recovery.py" backup "$@"
