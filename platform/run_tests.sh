#!/usr/bin/env bash
# run_tests.sh - test entry point for the environment core.
#
# Runs the unit suite, then the content policy that the application source is
# expected to satisfy. Both must pass. A suite that passes while the source
# violates its own stated policy is not a passing build.
#
# Exit codes: 0 both pass, 1 tests failed, 2 policy failed, 3 environment error.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLATFORM_ROOT="$(cd "$SCRIPT_DIR" && pwd)"
REPO_ROOT="$(cd "$PLATFORM_ROOT/.." && pwd)"

if command -v python3 >/dev/null 2>&1; then
  PYTHON=python3
else
  echo "python3 is required"
  exit 3
fi

echo "=== ENVIRONMENT CORE TESTS ==="
echo "root: $PLATFORM_ROOT"
echo

cd "$PLATFORM_ROOT"
"$PYTHON" -m unittest discover -s tests -t . -v 2>&1
TEST_EXIT=$?

echo
echo "=== CONTENT POLICY ==="

if [ -f "$PLATFORM_ROOT/policy.yaml" ] && [ -f "$REPO_ROOT/scripts/policy_scan.py" ]; then
  "$PYTHON" "$REPO_ROOT/scripts/policy_scan.py" --config "$PLATFORM_ROOT/policy.yaml" --root "$PLATFORM_ROOT"
  POLICY_EXIT=$?
else
  echo "no policy.yaml or no scanner available, policy enforced by the repository pipeline only"
  POLICY_EXIT=0
fi

echo
if [ "$TEST_EXIT" -ne 0 ]; then
  echo "RESULT: TESTS FAILED"
  exit 1
fi

if [ "$POLICY_EXIT" -ne 0 ]; then
  echo "RESULT: CONTENT POLICY FAILED"
  exit 2
fi

echo "RESULT: ALL PASS"
exit 0
