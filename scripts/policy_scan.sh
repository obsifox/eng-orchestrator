#!/usr/bin/env bash
# policy_scan.sh - wrapper for policy_scan.py with the control plane log contract.
# Writes .eng/artifacts/policy_scan.log ending in RESULT: and EXIT_CODE=, which is
# what gate_check.sh G6_Policy reads. A gate never trusts a claim, only this log.
# Usage: ./scripts/policy_scan.sh [--config <yaml>] [--root <dir>] [--rule <name>] [--out <log>] [--json]
# Exit codes: 0 PASS, 1 violations, 3 NOT APPLICABLE, 4 empty, 5 malformed, 6 error.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

CONFIG=""
ROOT="."
RULE="all"
OUT=".eng/artifacts/policy_scan.log"
JSON=0

usage() {
  echo "Usage: $0 [--config <yaml>] [--root <dir>] [--rule <name>] [--out <log>] [--json]"
  echo "Rules: all, comments, emoji, language, branding"
  echo "Config defaults to .eng/policy.yaml; without it the scan is NOT APPLICABLE."
  echo "Exit 0 PASS, 1 violations, 3 NOT APPLICABLE, 4 empty, 5 malformed, 6 error"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config) CONFIG="$2"; shift 2 ;;
    --root) ROOT="$2"; shift 2 ;;
    --rule) RULE="$2"; shift 2 ;;
    --out) OUT="$2"; shift 2 ;;
    --json) JSON=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1"; usage; exit 6 ;;
  esac
done

if [ -z "$CONFIG" ]; then
  for candidate in "$ROOT/.eng/policy.yaml" ".eng/policy.yaml"; do
    if [ -f "$candidate" ]; then CONFIG="$candidate"; break; fi
  done
fi

if [ -z "$CONFIG" ]; then
  CONFIG=".eng/policy.yaml"
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 is required for policy_scan"
  exit 6
fi

mkdir -p "$(dirname "$OUT")"

ARGS=(--config "$CONFIG" --root "$ROOT" --rule "$RULE")
if [ "$JSON" -eq 1 ]; then ARGS+=(--json); fi

python3 "$SCRIPT_DIR/policy_scan.py" "${ARGS[@]}" > "$OUT" 2>&1
EC=$?

echo "EXIT_CODE=$EC" >> "$OUT"
cat "$OUT"
exit $EC
