#!/usr/bin/env bash
# report_lint.sh - Rejects reports with claims lacking evidence
# Usage: ./scripts/report_lint.sh [--report <file>] [--evidence .eng/evidence.md] [--artifacts .eng/artifacts]
# Exit codes: 0 clean, 1 claim without evidence, 2 evidence file missing, 3 error
set -uo pipefail

REPORT_FILE=""
EVIDENCE_FILE=".eng/evidence.md"
ARTIFACTS_DIR=".eng/artifacts"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --report) REPORT_FILE="$2"; shift 2 ;;
    --evidence) EVIDENCE_FILE="$2"; shift 2 ;;
    --artifacts) ARTIFACTS_DIR="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: $0 [--report <delivery-report.md>] [--evidence <evidence.md>]"
      echo "Checks: PASS claims have evidence refs, no hallucinated metrics"
      echo "Exit 0 clean, 1 claim without evidence, 2 missing evidence file"
      exit 0
      ;;
    *) 
      if [ -z "$REPORT_FILE" ] && [ -f "$1" ]; then REPORT_FILE="$1"; fi
      shift
      ;;
  esac
done

# Find report if not specified
if [ -z "$REPORT_FILE" ]; then
  if [ -f "REPORT.md" ]; then REPORT_FILE="REPORT.md"
  elif [ -f ".eng/delivery-report.md" ]; then REPORT_FILE=".eng/delivery-report.md"
  elif ls .eng/*report*.md >/dev/null 2>&1; then REPORT_FILE=$(ls .eng/*report*.md | head -n1)
  else
    echo "No report file found, checking evidence only"
  fi
fi

FAIL=0

echo "=== REPORT LINT $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
echo "Report: ${REPORT_FILE:-none}"
echo "Evidence: $EVIDENCE_FILE"
echo "Artifacts: $ARTIFACTS_DIR"
echo ""

if [ ! -f "$EVIDENCE_FILE" ]; then
  echo "FAIL: Evidence file missing $EVIDENCE_FILE"
  exit 2
fi

# Check evidence file has at least one evidence entry
if ! grep -q "Evidence:" "$EVIDENCE_FILE"; then
  echo "FAIL: evidence.md has no Evidence entries"
  FAIL=1
fi

# If report exists, check claims
if [ -n "$REPORT_FILE" ] && [ -f "$REPORT_FILE" ]; then
  echo "--- Checking report $REPORT_FILE ---"
  
  # Forbidden phrases without evidence
  # Look for PASS claims
  if grep -i -n "PASS" "$REPORT_FILE" | grep -v -i "evidence\|log\|\.eng\|artifacts\|NOT TESTED" | grep -i "PASS" ; then
    echo "WARNING: Found PASS mentions without evidence ref pattern, manual check needed"
    # Not auto-fail, but flag
  fi

  # Check for hallucinated performance claims
  if grep -i -E "highly performant|extremely fast|100% secure|no vulnerabilities|perfect" "$REPORT_FILE" 2>/dev/null; then
    echo "FAIL: Found sycophantic/hallucinated claim without measurement:"
    grep -i -n -E "highly performant|extremely fast|100% secure|no vulnerabilities|perfect" "$REPORT_FILE"
    FAIL=1
  fi

  # Check that every SOLVED has evidence ref in report or evidence.md
  # Count SOLVED in report
  SOLVED_COUNT=$(grep -c "SOLVED" "$REPORT_FILE" || true)
  EVIDENCE_COUNT=$(grep -c "Evidence:" "$EVIDENCE_FILE" || true)
  echo "SOLVED mentions in report: $SOLVED_COUNT, Evidence entries: $EVIDENCE_COUNT"
  if [ "$SOLVED_COUNT" -gt "$EVIDENCE_COUNT" ] && [ "$SOLVED_COUNT" -gt 0 ]; then
    echo "WARNING: More SOLVED claims than evidence entries"
    # Not fail if report references logs
    if ! grep -q "\.eng/artifacts" "$REPORT_FILE"; then
      echo "FAIL: SOLVED without artifact refs"
      FAIL=1
    fi
  fi

  # Check gates have evidence
  for gate in "G0" "G1" "G2" "G3" "G4"; do
    if grep -q "$gate.*PASS" "$REPORT_FILE"; then
      if ! grep -q "$gate" "$EVIDENCE_FILE"; then
        echo "FAIL: Gate $gate marked PASS in report but no evidence in evidence.md"
        FAIL=1
      fi
    fi
  done

else
  echo "No report file, only evidence check"
fi

# Check artifacts dir exists and has logs
if [ ! -d "$ARTIFACTS_DIR" ]; then
  echo "WARNING: Artifacts dir missing $ARTIFACTS_DIR"
else
  echo "Artifacts:"
  ls -lh "$ARTIFACTS_DIR" | head -n 20
  if [ "$(ls -A "$ARTIFACTS_DIR" 2>/dev/null | wc -l)" -eq 0 ]; then
    echo "FAIL: Artifacts dir empty, no evidence logs"
    FAIL=1
  fi
fi

echo ""
if [ $FAIL -eq 0 ]; then
  echo "RESULT: PASS - report lint clean"
  exit 0
else
  echo "RESULT: FAIL - claims without evidence or hallucinated metrics"
  exit 1
fi
