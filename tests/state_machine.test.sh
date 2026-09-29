#!/usr/bin/env bash
# state_machine.test.sh - 37 transition tests v1.1
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

PASS=0
FAIL=0

assert_valid() {
  local from="$1" to="$2" name="$3"
  local out
  out=$(./scripts/state_machine.sh validate --from "$from" --to "$to" 2>&1 || true)
  if echo "$out" | grep -q "VALID" && ! echo "$out" | grep -q "INVALID"; then
    echo "  ✅ $name $from->$to VALID PASS"
    PASS=$((PASS+1))
  else
    echo "  ❌ $name $from->$to should be VALID FAIL (got: $out)"
    FAIL=$((FAIL+1))
  fi
}

assert_invalid() {
  local from="$1" to="$2" name="$3"
  local out
  out=$(./scripts/state_machine.sh validate --from "$from" --to "$to" 2>&1 || true)
  if echo "$out" | grep -q "INVALID"; then
    echo "  ✅ $name $from->$to INVALID PASS"
    PASS=$((PASS+1))
  else
    echo "  ❌ $name $from->$to should be INVALID FAIL (got: $out)"
    FAIL=$((FAIL+1))
  fi
}

echo "=== STATE MACHINE TESTS v1.1 - 37 transitions ==="

# Valid transitions (should PASS)
assert_valid "INTAKE" "BASELINE" "V1"
assert_valid "BASELINE" "CLASSIFICATION" "V2"
assert_valid "CLASSIFICATION" "PLANNING" "V3"
assert_valid "PLANNING" "EXECUTION" "V4"
assert_valid "EXECUTION" "VALIDATION" "V5"
assert_valid "VALIDATION" "REVIEW" "V6"
assert_valid "REVIEW" "VERIFICATION" "V7"
assert_valid "REVIEW" "REWORK" "V8"
assert_valid "REWORK" "VALIDATION" "V9"
assert_valid "REWORK" "ESCALATED" "V10"
assert_valid "VERIFICATION" "RELEASE_REVIEW" "V11"
assert_valid "RELEASE_REVIEW" "HUMAN_APPROVAL" "V12"
assert_valid "RELEASE_REVIEW" "COMPLETED" "V13"
assert_valid "HUMAN_APPROVAL" "COMPLETED" "V14"
assert_valid "HUMAN_APPROVAL" "CANCELLED" "V15"
assert_valid "ESCALATED" "HUMAN_APPROVAL" "V16"
assert_valid "ESCALATED" "RECOVERY" "V17"
assert_valid "RECOVERY" "EXECUTION" "V18"
assert_valid "RECOVERY" "FAILED" "V19"
assert_valid "EXECUTION" "FAILED" "V20 wildcard"
assert_valid "EXECUTION" "BLOCKED" "V21 wildcard"
assert_valid "PLANNING" "CANCELLED" "V22 wildcard"

# Invalid transitions (should be INVALID)
assert_invalid "EXECUTION" "COMPLETED" "I1 must go through validation"
assert_invalid "INTAKE" "COMPLETED" "I2 must complete lifecycle"
assert_invalid "PLANNING" "VERIFICATION" "I3 missing execution"
assert_invalid "BASELINE" "EXECUTION" "I4 missing classification planning"
assert_invalid "VALIDATION" "COMPLETED" "I5 missing review verification"
assert_invalid "CLASSIFICATION" "EXECUTION" "I6 missing planning"
assert_invalid "INTAKE" "REVIEW" "I7 missing steps"
assert_invalid "COMPLETED" "EXECUTION" "I8 terminal cannot go to execution"
assert_invalid "FAILED" "PLANNING" "I9 terminal cannot go back"
assert_invalid "CANCELLED" "EXECUTION" "I10 terminal cannot resume without recovery"
assert_invalid "BLOCKED" "COMPLETED" "I11 blocked cannot complete directly"
assert_invalid "REVIEW" "COMPLETED" "I12 review cannot complete directly"
assert_invalid "PLANNING" "COMPLETED" "I13 planning cannot complete"
assert_invalid "BASELINE" "COMPLETED" "I14 baseline cannot complete"
assert_invalid "INTAKE" "VERIFICATION" "I15 intake cannot verify"

echo ""
echo "=== SUMMARY ==="
echo "PASS: $PASS"
echo "FAIL: $FAIL"
echo "Total: $((PASS+FAIL))"
if [ $FAIL -eq 0 ]; then
  echo "RESULT: ALL STATE MACHINE TESTS PASS (37)"
  exit 0
else
  echo "RESULT: SOME FAIL"
  exit 1
fi
