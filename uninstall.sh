#!/bin/sh
set -eu
PROJECT_ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd -P)
exec "${PYTHON:-python3}" "$PROJECT_ROOT/scripts/manage_install.py" uninstall "$@"
