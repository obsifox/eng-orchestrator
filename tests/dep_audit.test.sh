#!/usr/bin/env bash
# tests/dep_audit.test.sh - the dependency audit's manifest handling.
#
# The audit exists to answer one question: can a vulnerable dependency reach a release? That
# makes classification the important part - a dev-only manifest, a nested test harness and a
# shipped runtime dependency must not all end up as the same line in a log.
#
# 12 asserts.
set -uo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

PASS=0
FAIL=0

assert_eq() {
  local expected="$1" actual="$2" name="$3"
  if [ "$expected" = "$actual" ]; then
    echo "  ✅ $name (expected=$expected actual=$actual)"
    PASS=$((PASS + 1))
  else
    echo "  ❌ $name (expected=$expected actual=$actual)"
    FAIL=$((FAIL + 1))
  fi
}

assert_contains() {
  local file="$1" needle="$2" name="$3"
  if grep -qF -- "$needle" "$file" 2>/dev/null; then
    echo "  ✅ $name"
    PASS=$((PASS + 1))
  else
    echo "  ❌ $name (not found in $file: $needle)"
    FAIL=$((FAIL + 1))
  fi
}

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

run_audit() {
  ( cd "$1" && bash "$REPO_ROOT/scripts/dep_audit.sh" --out "$1/audit.log" >/dev/null 2>&1; echo $? )
}

echo "--- T1: no manifest at all -> NOT APPLICABLE (3) ---"
mkdir -p "$WORK/empty"
code="$(run_audit "$WORK/empty")"
assert_eq 3 "$code" "T1 exit code"
assert_contains "$WORK/empty/audit.log" "RESULT: NOT APPLICABLE" "T1 log says NOT APPLICABLE"

echo "--- T2: dev-only composer.json -> NOT APPLICABLE (3), named as dev-only ---"
mkdir -p "$WORK/phpdev"
cat > "$WORK/phpdev/composer.json" <<'JSON'
{"name": "acme/plugin", "require-dev": {"phpunit/phpunit": "^11"}, "scripts": {"test": "phpunit"}}
JSON
code="$(run_audit "$WORK/phpdev")"
assert_eq 3 "$code" "T2 exit code"
assert_contains "$WORK/phpdev/audit.log" "dev-only: ./composer.json" "T2 names the manifest as dev-only"

echo "--- T3: nested test harness with dependencies -> tooling, not runtime (3) ---"
mkdir -p "$WORK/tooling/tests/e2e"
echo '{"name":"e2e","dependencies":{"playwright":"^1.40.0"}}' > "$WORK/tooling/tests/e2e/package.json"
code="$(run_audit "$WORK/tooling")"
assert_eq 3 "$code" "T3 exit code"
assert_contains "$WORK/tooling/audit.log" "tooling (nested, does not ship): ./tests/e2e/package.json" "T3 labels the nested manifest"

echo "--- T4: a shipped runtime dependency with no lockfile -> NOT TESTED (2) ---"
mkdir -p "$WORK/ships"
echo '{"name":"app","dependencies":{"left-pad":"^1.0.0"}}' > "$WORK/ships/package.json"
code="$(run_audit "$WORK/ships")"
assert_eq 2 "$code" "T4 exit code (never NOT APPLICABLE for shipped code)"
assert_contains "$WORK/ships/audit.log" "no lockfile" "T4 says why"

echo "--- T5: both kinds in one repository are reported separately ---"
mkdir -p "$WORK/both/tests/e2e"
echo '{"name":"app","dependencies":{"left-pad":"^1.0.0"}}' > "$WORK/both/package.json"
echo '{"name":"e2e","devDependencies":{"playwright":"^1.40.0"}}' > "$WORK/both/tests/e2e/package.json"
code="$(run_audit "$WORK/both")"
assert_eq 2 "$code" "T5 exit code (the shipped manifest decides)"
assert_contains "$WORK/both/audit.log" "runtime:  ./package.json" "T5 the root manifest is runtime"

echo "--- T6: a platform floor (php only) is not a runtime dependency ---"
mkdir -p "$WORK/platform"
cat > "$WORK/platform/composer.json" <<'JSON'
{"name": "acme/plugin", "require": {"php": ">=8.0", "ext-json": "*"}, "require-dev": {"phpunit/phpunit": "^11"}}
JSON
code="$(run_audit "$WORK/platform")"
assert_eq 3 "$code" "T6 exit code (a platform floor pulls in no code)"
assert_contains "$WORK/platform/audit.log" "dev-only: ./composer.json" "T6 classified as dev-only"

echo ""
echo "PASS: $PASS"
echo "FAIL: $FAIL"
echo "Total: $((PASS + FAIL))"

if [ "$FAIL" -gt 0 ]; then
  echo "RESULT: SOME TESTS FAIL"
  exit 1
fi

echo "RESULT: ALL DEP AUDIT TESTS PASS"
