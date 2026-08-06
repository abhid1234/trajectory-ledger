#!/bin/sh
set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHON_BIN=${PYTHON_BIN:-python3.11}
DEMO_PARENT=$(mktemp -d "${TMPDIR:-/tmp}/trajectory-ledger-demo.XXXXXX")
DEMO_OUTPUT="$DEMO_PARENT/artifacts"

cd "$PROJECT_DIR"
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. "$PYTHON_BIN" -m trajectory_ledger.cli \
  fixtures/demo_redacted_tainted.json "$DEMO_OUTPUT" --attest abstain
