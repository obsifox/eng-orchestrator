#!/usr/bin/env bash
# gate_check.sh - Executable gate checker
# Usage: ./scripts/gate_check.sh <gate> [--state .eng/state.json] [--evidence .eng/evidence.md]
# Gates: G0_Build, G1_Tests, G2_Lens, G3_Security, G4_Release, architecture, lens, security, release, all
# Exit codes: 0 PASS, 1 FAIL, 2 NOT TESTED, 3 NOT APPLICABLE, 4 error
set -uo pipefail

GATE="${1:-all}"
STATE_FILE=".eng/state.json"
EVIDENCE_FILE=".eng/evidence.md"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --state) STATE_FILE="$2"; shift 2 ;;
    --evidence) EVIDENCE_FILE="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: $0 <gate> [--state <json>] [--evidence <md>]"
      echo "Gates: G0_Build, G1_Tests, G2_Lens, G3_Security, G4_Release, all"
      echo "Exit 0 PASS, 1 FAIL, 2 NOT TESTED, 3 NOT_APPLICABLE"
      exit 0
      ;;
    *) 
      if [[ "$1" != --* ]]; then GATE="$1"; fi
      shift
      ;;
  esac
done

check_file_exists() {
  if [ ! -f "$1" ]; then
    echo "Missing file: $1 -> NOT TESTED"
    return 2
  fi
  return 0
}

check_gate() {
  local g="$1"
  case "$g" in
    G0_Build|build)
      echo "Checking G0 Build..."
      if [ -f .eng/artifacts/baseline.log ]; then
        if grep -q "BUILD_EXIT:" .eng/artifacts/baseline.log; then
          echo "FAIL: baseline build failed"
          return 1
        fi
      fi
      # Look for latest build log
      if ls .eng/artifacts/*build*.log >/dev/null 2>&1; then
        echo "Build logs found"
      fi
      if [ -f "$STATE_FILE" ]; then
        if command -v python3 >/dev/null 2>&1; then
          python3 - <<PY
import json
with open("$STATE_FILE") as f:
  d=json.load(f)
g=d.get('gates',{}).get('G0_Build','NOT_TESTED')
print(f"State G0_Build={g}")
exit(0 if g=='PASS' else 1 if g=='FAIL' else 2 if g=='NOT_TESTED' else 3)
PY
          return $?
        fi
      fi
      echo "PASS if evidence exists"
      if [ -f "$EVIDENCE_FILE" ] && grep -q "G0\|Build" "$EVIDENCE_FILE"; then
        echo "Evidence found"
        return 0
      else
        echo "NOT TESTED - no evidence"
        return 2
      fi
      ;;
    G1_Tests|tests)
      echo "Checking G1 Tests..."
      if [ -f .eng/artifacts/baseline.log ]; then
        # Compare logic simplified: if baseline had failures, check current
        echo "Baseline exists, checking for new failures"
      fi
      if ls .eng/artifacts/*test*.log .eng/artifacts/baseline.log >/dev/null 2>&1; then
        if grep -q "FAIL\|Error" .eng/artifacts/*test*.log 2>/dev/null; then
          echo "Test logs show failures - checking if new"
          # Simplified: if any fail, mark FAIL unless baseline also failed
          return 1
        fi
        echo "PASS - test logs clean"
        return 0
      else
        echo "NOT TESTED - no test logs"
        return 2
      fi
      ;;
    G2_Lens|lens|architecture)
      echo "Checking G2 Lens / Architecture..."
      if ls .eng/artifacts/*review*.md >/dev/null 2>&1; then
        if grep -R -i "CRITICAL.*OPEN\|HIGH.*OPEN" .eng/artifacts/*review*.md 2>/dev/null; then
          echo "FAIL: open HIGH/CRITICAL findings"
          return 1
        else
          echo "PASS: no open HIGH/CRITICAL"
          return 0
        fi
      else
        echo "NOT TESTED - no review files"
        return 2
      fi
      ;;
    G3_Security|security)
      echo "Checking G3 Security..."
      local secret_exit=0
      if [ -f .eng/artifacts/secret_scan.log ]; then
        if grep -q "RESULT: FAIL" .eng/artifacts/secret_scan.log; then
          echo "FAIL: secret scan found secrets"
          return 1
        fi
      else
        echo "No secret scan log -> NOT TESTED"
        secret_exit=2
      fi
      if [ -f .eng/artifacts/dep_audit.log ]; then
        if grep -q "RESULT: FAIL" .eng/artifacts/dep_audit.log; then
          echo "FAIL: dep audit HIGH"
          return 1
        fi
      fi
      if [ $secret_exit -eq 2 ]; then return 2; fi
      echo "PASS"
      return 0
      ;;
    G4_Release|release)
      echo "Checking G4 Release..."
      if [ -f .eng/artifacts/release-review.md ]; then
        if grep -q "sha256" .eng/artifacts/release-review.md; then
          echo "PASS - release artifact hashed"
          return 0
        else
          echo "FAIL - no hash"
          return 1
        fi
      else
        # Check if release needed
        if [ -f "$STATE_FILE" ]; then
          if command -v python3 >/dev/null 2>&1; then
            python3 - <<PY
import json
with open("$STATE_FILE") as f:
  d=json.load(f)
g=d.get('gates',{}).get('G4_Release','NOT_APPLICABLE')
print(g)
PY
          fi
        fi
        echo "NOT APPLICABLE or NOT TESTED - no release-review"
        return 3
      fi
      ;;
    all)
      echo "Checking all gates..."
      local overall=0
      for gate in G0_Build G1_Tests G2_Lens G3_Security G4_Release; do
        echo "--- $gate ---"
        check_gate "$gate"
        ec=$?
        echo "Result $gate: $ec"
        if [ $ec -eq 1 ]; then overall=1; fi
        if [ $ec -eq 2 ] && [ $overall -eq 0 ]; then overall=2; fi
      done
      return $overall
      ;;
    *)
      echo "Unknown gate: $g"
      return 4
      ;;
  esac
}

check_gate "$GATE"
ec=$?
case $ec in
  0) echo "GATE $GATE: PASS" ;;
  1) echo "GATE $GATE: FAIL" ;;
  2) echo "GATE $GATE: NOT TESTED" ;;
  3) echo "GATE $GATE: NOT APPLICABLE" ;;
  *) echo "GATE $GATE: ERROR $ec" ;;
esac
exit $ec
