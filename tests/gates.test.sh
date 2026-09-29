#!/usr/bin/env bash
# gates.test.sh - Regression tests for gate fixes v1.0.1
# Tests T1-T10 from bugfix guide
# Each test is a fixture with expected exit codes
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

PASS=0
FAIL=0

# Helpers
setup_clean() {
  rm -rf .eng/artifacts
  mkdir -p .eng/artifacts
  rm -f package.json package-lock.json
}

assert_exit() {
  local expected="$1" actual="$2" name="$3"
  if [ "$expected" = "$actual" ]; then
    echo "  ✅ $name expected=$expected actual=$actual PASS"
    PASS=$((PASS+1))
  else
    echo "  ❌ $name expected=$expected actual=$actual FAIL"
    FAIL=$((FAIL+1))
  fi
}

echo "=== GATE REGRESSION TESTS v1.0.1 ==="
echo "Repo root: $REPO_ROOT"
echo ""

# T1: build and test healthy
echo "--- T1: build and test healthy -> G0=0 G1=0 ---"
setup_clean
cat > package.json <<'JSON'
{"name":"test","scripts":{"build":"echo building ok","test":"echo tests ok && exit 0"}}
JSON
echo '{}' > package-lock.json
./scripts/baseline.sh >/dev/null 2>&1
# baseline should have EXIT_CODE 0 for both
base_build=$(grep '^EXIT_CODE=' .eng/artifacts/baseline_build.log | cut -d= -f2)
base_test=$(grep '^EXIT_CODE=' .eng/artifacts/baseline_test.log | cut -d= -f2)
assert_exit 0 "$base_build" "T1 baseline_build"
assert_exit 0 "$base_test" "T1 baseline_test"
./scripts/gate_check.sh G0_Build --no-run >/dev/null 2>&1; ec=$?
# With --no-run, G0 checks current_build.log, not yet exists -> need run without --no-run or create current
./scripts/gate_check.sh G0_Build >/dev/null 2>&1; ec=$?
assert_exit 0 "$ec" "T1 G0_Build"
./scripts/gate_check.sh G1_Tests >/dev/null 2>&1; ec=$?
assert_exit 0 "$ec" "T1 G1_Tests"
echo ""

# T2: test failing
echo "--- T2: test failing -> G1=1 ---"
setup_clean
cat > package.json <<'JSON'
{"name":"test","scripts":{"build":"echo ok","test":"echo fail && exit 1"}}
JSON
echo '{}' > package-lock.json
./scripts/baseline.sh >/dev/null 2>&1
./scripts/gate_check.sh G1_Tests >/dev/null 2>&1; ec=$?
assert_exit 1 "$ec" "T2 G1_Tests should FAIL"
echo ""

# T3: build broken after healthy baseline, with state.json PASS (should still FAIL)
echo "--- T3: build broken after baseline healthy, state.json says PASS -> G0=1 (must not trust state.json) ---"
setup_clean
cat > package.json <<'JSON'
{"name":"test","scripts":{"build":"echo healthy","test":"echo ok"}}
JSON
echo '{}' > package-lock.json
./scripts/baseline.sh >/dev/null 2>&1
# Now break build
cat > package.json <<'JSON'
{"name":"test","scripts":{"build":"echo broken && exit 2","test":"echo ok"}}
JSON
# Create fake state.json claiming PASS
mkdir -p .eng
cat > .eng/state.json <<'JSON'
{"version":"1.0.0","gates":{"G0_Build":"PASS","G1_Tests":"PASS","G2_Lens":"PASS","G3_Security":"PASS","G4_Release":"NOT_APPLICABLE"}}
JSON
./scripts/gate_check.sh G0_Build >/dev/null 2>&1; ec=$?
assert_exit 1 "$ec" "T3 G0 should FAIL despite state.json PASS"
echo ""

# T4: build broken in baseline
echo "--- T4: build broken in baseline -> G0=1 ---"
setup_clean
cat > package.json <<'JSON'
{"name":"test","scripts":{"build":"exit 3","test":"echo ok"}}
JSON
echo '{}' > package-lock.json
./scripts/baseline.sh >/dev/null 2>&1
./scripts/gate_check.sh G0_Build >/dev/null 2>&1; ec=$?
assert_exit 1 "$ec" "T4 G0 baseline broken should FAIL"
echo ""

# T5: review with severity=HIGH status=CLOSED -> G2=0
echo "--- T5: review severity=HIGH status=CLOSED -> G2=0 ---"
setup_clean
cat > .eng/artifacts/security-review.md <<'MD'
- [F-001] severity=HIGH status=CLOSED | Fixed SQL injection | src/login.php:10
MD
./scripts/gate_check.sh G2_Lens --no-run >/dev/null 2>&1; ec=$?
assert_exit 0 "$ec" "T5 G2 CLOSED should PASS"
echo ""

# T6: review with status=OPEN severity=HIGH (order reversed) -> G2=1
echo "--- T6: review status=OPEN severity=HIGH (order reversed) -> G2=1 ---"
setup_clean
cat > .eng/artifacts/arch-review.md <<'MD'
- [F-002] status=OPEN severity=HIGH | Circular dep | src/a.ts
MD
./scripts/gate_check.sh G2_Lens --no-run >/dev/null 2>&1; ec=$?
assert_exit 1 "$ec" "T6 G2 OPEN HIGH reversed order should FAIL"
echo ""

# T7: secret planted -> secret_scan exit 1 and G3=1
# Use generic SECRET_KEY pattern (not Stripe) to avoid GitHub push protection
echo "--- T7: secret planted -> secret_scan exit=1 and G3=1 ---"
setup_clean
echo 'SECRET_KEY = "my-very-secret-value-12345"' > test_secret_file.txt
./scripts/secret_scan.sh --path . >/dev/null 2>&1; ec=$?
assert_exit 1 "$ec" "T7 secret_scan should FAIL"
# Need dep_audit log to exist for G3 check, create dummy PASS
echo "RESULT: PASS - No HIGH" > .eng/artifacts/dep_audit.log
./scripts/gate_check.sh G3_Security --no-run >/dev/null 2>&1; ec=$?
assert_exit 1 "$ec" "T7 G3 should FAIL due to secret"
rm -f test_secret_file.txt
echo ""

# T8: clean repo but dep_audit.log missing -> G3=2 NOT TESTED
echo "--- T8: clean repo but dep_audit.log missing -> G3=2 ---"
setup_clean
./scripts/secret_scan.sh --path . >/dev/null 2>&1
# No dep_audit.log
rm -f .eng/artifacts/dep_audit.log
./scripts/gate_check.sh G3_Security --no-run >/dev/null 2>&1; ec=$?
assert_exit 2 "$ec" "T8 G3 missing dep_audit should be NOT TESTED=2"
echo ""

# T9: npm project without lockfile -> dep_audit exit 2 NOT TESTED
echo "--- T9: npm project without lockfile -> dep_audit exit 2 NOT TESTED ---"
setup_clean
cat > package.json <<'JSON'
{"name":"test","dependencies":{"lodash":"4.17.21"}}
JSON
rm -f package-lock.json yarn.lock
./scripts/dep_audit.sh >/dev/null 2>&1; ec=$?
assert_exit 2 "$ec" "T9 dep_audit no lockfile should be 2"
# Check log contains NOT TESTED
if grep -q "NOT TESTED" .eng/artifacts/dep_audit.log; then
  echo "  ✅ T9 dep_audit log contains NOT TESTED PASS"
  PASS=$((PASS+1))
else
  echo "  ❌ T9 dep_audit log missing NOT TESTED FAIL"
  FAIL=$((FAIL+1))
fi
echo ""

# T10: report SOLVED with empty evidence -> report_lint exit 1
echo "--- T10: report SOLVED with empty evidence -> report_lint exit 1 ---"
setup_clean
mkdir -p .eng
cat > .eng/evidence.md <<'MD'
# Evidence Ledger
## BASELINE
- Build: none
MD
cat > REPORT.md <<'MD'
# Report
## Features
- T1 SOLVED - Implemented login
G0 Build: PASS
MD
mkdir -p .eng/artifacts
touch .eng/artifacts/dummy.log
./scripts/report_lint.sh --report REPORT.md >/dev/null 2>&1; ec=$?
assert_exit 1 "$ec" "T10 report_lint should FAIL for SOLVED without evidence"
rm -f REPORT.md
echo ""

# Summary
echo "=== SUMMARY ==="
echo "PASS: $PASS"
echo "FAIL: $FAIL"
echo "Total: $((PASS+FAIL))"
if [ $FAIL -eq 0 ]; then
  echo "RESULT: ALL TESTS PASS"
  exit 0
else
  echo "RESULT: SOME TESTS FAIL"
  exit 1
fi
