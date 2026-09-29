#!/usr/bin/env bash
# permissions.test.sh - 21 authorization tests v1.1
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

PASS=0
FAIL=0

assert_allow() {
  local agent="$1" tool="$2" name="$3"
  local out
  out=$(./scripts/permission_check.sh check --agent "$agent" --tool "$tool" 2>&1 || true)
  if echo "$out" | grep -q "ALLOW"; then
    echo "  ✅ $name $agent can $tool ALLOW PASS"
    PASS=$((PASS+1))
  else
    echo "  ❌ $name $agent can $tool should ALLOW FAIL (got: $out)"
    FAIL=$((FAIL+1))
  fi
}

assert_deny() {
  local agent="$1" tool="$2" name="$3"
  local out
  out=$(./scripts/permission_check.sh check --agent "$agent" --tool "$tool" 2>&1 || true)
  if echo "$out" | grep -q "DENY"; then
    echo "  ✅ $name $agent cannot $tool DENY PASS"
    PASS=$((PASS+1))
  else
    echo "  ❌ $name $agent cannot $tool should DENY FAIL (got: $out)"
    FAIL=$((FAIL+1))
  fi
}

echo "=== PERMISSION TESTS v1.1 - 21 tests ==="

# Worker should be able to write
assert_allow "worker" "write_file" "P1"
assert_allow "worker" "read_file" "P2"
assert_allow "worker" "bash" "P3"

# Reviewer should NOT write
assert_deny "reviewer" "write_file" "P4"
assert_allow "reviewer" "read_file" "P5"
assert_deny "reviewer" "bash" "P6" # bash requires execute, reviewer has restricted

# Architect read only
assert_allow "architect" "read_file" "P7"
assert_deny "architect" "write_file" "P8"

# Security reviewer cannot read secrets
assert_deny "security-reviewer" "secret_read" "P9"
assert_allow "security-reviewer" "read_file" "P10"

# Verifier cannot write
assert_deny "verifier" "write_file" "P11"
assert_allow "verifier" "read_file" "P12"

# Release manager can write
assert_allow "release-manager" "write_file" "P13"
assert_allow "release-manager" "bash" "P14"

# Human can do everything
assert_allow "human" "write_file" "P15"
assert_allow "human" "bash" "P16"
assert_allow "human" "read_file" "P17"

# Worker cannot read secrets
assert_deny "worker" "secret_read" "P18"

# Reviewer cannot read secrets
assert_deny "reviewer" "secret_read" "P19"

# Architect cannot read secrets
assert_deny "architect" "secret_read" "P20"

# Verifier cannot read secrets
assert_deny "verifier" "secret_read" "P21"

echo ""
echo "=== SUMMARY ==="
echo "PASS: $PASS"
echo "FAIL: $FAIL"
if [ $FAIL -eq 0 ]; then
  echo "RESULT: ALL PERMISSION TESTS PASS (21)"
  exit 0
else
  echo "RESULT: SOME FAIL"
  exit 1
fi
