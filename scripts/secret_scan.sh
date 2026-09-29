#!/usr/bin/env bash
# secret_scan.sh - Lightweight secret scan, no deps
# Usage: ./scripts/secret_scan.sh [--path .] [--out .eng/artifacts/secret_scan.log]
# Exit codes: 0 no secrets found, 1 secrets found, 2 error
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

# Patterns - careful to avoid false positives but catch obvious
PATTERNS=(
  "AKIA[0-9A-Z]{16}" # AWS key
  "ghp_[A-Za-z0-9]{36}" # github pat
  "github_pat_"
  "BEGIN RSA PRIVATE KEY"
  "BEGIN OPENSSH PRIVATE KEY"
  "sk_live_[0-9a-zA-Z]{24}" # stripe
  "xox[bpras]-[0-9a-zA-Z-]{10,}"
  "password\s*=\s*['\"][^'\"]{3,}['\"]"
  "api_key\s*=\s*['\"][^'\"]{8,}['\"]"
  "SECRET_KEY\s*=\s*['\"][^'\"]{8,}['\"]"
)

FOUND=0
{
  echo "=== SECRET SCAN $(date -u +%Y-%m-%dT%H:%M:%SZ) PATH=$SCAN_PATH ==="
  echo "Excluding: .git, node_modules, .eng/artifacts, dist, build, .venv, __pycache__"
  echo ""

  # Build exclude args for grep
  EXCLUDE_DIRS=(.git node_modules .eng dist build .venv __pycache__ .next out target vendor)
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

  # Check .env files not committed but present
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
  if [ $FOUND -eq 0 ]; then
    echo "RESULT: PASS - No obvious secrets found"
  else
    echo "RESULT: FAIL - Potential secrets found, review above"
  fi

} | tee "$OUT"

if [ $FOUND -eq 0 ]; then exit 0; else exit 1; fi
