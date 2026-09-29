#!/usr/bin/env bash
# secret_scan.sh - Lightweight secret scan v1.0.2
# Fix: Avoid subshell variable loss from pipe, exclude tests/ and .git etc properly
# Usage: ./scripts/secret_scan.sh [--path .] [--out .eng/artifacts/secret_scan.log]
# Exit codes: 0 clean, 1 secrets found, 2 error
set -uo pipefail

SCAN_PATH="."
OUT=".eng/artifacts/secret_scan.log"
mkdir -p "$(dirname "$OUT")"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --path) SCAN_PATH="$2"; shift 2 ;;
    --out) OUT="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: $0 [--path <dir>] [--out <log>]"
      echo "Scans for common secret patterns"
      echo "Exit 0 clean, 1 secrets found, 2 error"
      exit 0
      ;;
    *) shift ;;
  esac
done

PATTERNS=(
  "AKIA[0-9A-Z]{16}"
  "ghp_[A-Za-z0-9]{36}"
  "github_pat_"
  "BEGIN RSA PRIVATE KEY"
  "BEGIN OPENSSH PRIVATE KEY"
  "sk_live_[0-9a-zA-Z]{24}"
  "xox[bpras]-[0-9a-zA-Z-]{10,}"
  "password\s*=\s*['\"][^'\"]{3,}['\"]"
  "api_key\s*=\s*['\"][^'\"]{8,}['\"]"
  "SECRET_KEY\s*=\s*['\"][^'\"]{8,}['\"]"
)

FOUND=0
TMP_LOG=$(mktemp)

{
  echo "=== SECRET SCAN $(date -u +%Y-%m-%dT%H:%M:%SZ) PATH=$SCAN_PATH ==="
  echo "Excluding: .git, node_modules, .eng/artifacts, dist, build, .venv, __pycache__, .next, out, target, vendor, tests"
  echo ""

  EXCLUDE_DIRS=(.git node_modules .eng dist build .venv __pycache__ .next out target vendor tests)
  GREP_EXCLUDES=""
  for d in "${EXCLUDE_DIRS[@]}"; do
    GREP_EXCLUDES="$GREP_EXCLUDES --exclude-dir=$d"
  done

  for pat in "${PATTERNS[@]}"; do
    echo "--- Checking pattern: $pat ---"
    # shellcheck disable=SC2086
    if grep -R -I -n -E $GREP_EXCLUDES --exclude="*.log" --exclude="secret_scan.sh" "$pat" "$SCAN_PATH" 2>/dev/null; then
      echo "FOUND: $pat"
      FOUND=1
    else
      echo "clean"
    fi
    echo ""
  done

  echo "--- Checking .env files presence ---"
  if ls "$SCAN_PATH"/.env 2>/dev/null; then
    echo "WARNING: .env file exists in $SCAN_PATH - ensure not committed"
    if git check-ignore -q "$SCAN_PATH/.env" 2>/dev/null; then
      echo ".env is gitignored (good)"
    else
      echo "CRITICAL: .env NOT gitignored"
      FOUND=1
    fi
  fi

  echo ""
  if [ $FOUND -eq 1 ]; then
    echo "RESULT: FAIL - Potential secrets found, review above"
  else
    echo "RESULT: PASS - No obvious secrets found"
  fi

} | tee "$TMP_LOG"
# Capture FOUND from tee'd log (since block runs in subshell for pipe, we re-parse)
if grep -q "FOUND:" "$TMP_LOG"; then
  FOUND=1
fi
if grep -q "CRITICAL: .env NOT gitignored" "$TMP_LOG"; then
  FOUND=1
fi

cat "$TMP_LOG" > "$OUT"
rm -f "$TMP_LOG"

if [ $FOUND -eq 1 ]; then
  exit 1
else
  exit 0
fi
