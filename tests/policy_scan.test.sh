#!/usr/bin/env bash
# policy_scan.test.sh - content policy scanner + G6_Policy gate (v2.2)
# 34 asserts. Every assertion executes the scanner or the gate; nothing is claimed.
#
# Note on style: the other suites in this directory print PASS with a pictograph.
# This suite does not, because it tests the emoji rule and would otherwise be the
# first finding its own scanner reports.
#
# Note on pipefail: policy_scan.py exits 1 when it finds violations, so a pipeline
# ending in grep inherits that status. Output is captured before matching.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SCRIPTS="$REPO_ROOT/scripts"
FIXTURES="$REPO_ROOT/tests/fixtures/policy"
CONFIGS="$REPO_ROOT/tests/fixtures/policy-config"

PASS=0
FAIL=0
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

cd "$REPO_ROOT"

ok()    { echo "  [PASS] $1"; PASS=$((PASS+1)); }
bad()   { echo "  [FAIL] $1"; FAIL=$((FAIL+1)); }
check() { if [ "$2" = "$3" ]; then ok "$1"; else echo "        expected=$2 got=$3"; bad "$1"; fi; }

scan_output() {
  python3 "$SCRIPTS/policy_scan.py" --config "$1" --root "$REPO_ROOT" 2>/dev/null || true
}

scan_exit() {
  python3 "$SCRIPTS/policy_scan.py" --config "$1" --root "$REPO_ROOT" > /dev/null 2>&1
  local code=$?
  echo "$code"
}

count_matches() {
  local output
  output="$(scan_output "$1")"
  printf '%s\n' "$output" | grep -c -- "$2" || true
}

expect_found() {
  local name="$1" config="$2" needle="$3" found
  found="$(count_matches "$config" "$needle")"
  if [ "$found" -gt 0 ]; then ok "$name"; else echo "        no match for: $needle"; bad "$name"; fi
}

expect_absent() {
  local name="$1" config="$2" needle="$3"
  check "$name" "0" "$(count_matches "$config" "$needle")"
}

echo "=== POLICY SCAN TESTS v2.2 ==="
echo "Repo root: $REPO_ROOT"
echo ""

echo "--- configuration handling ---"

check "P1 missing config is NOT APPLICABLE" "3" "$(scan_exit "$TMP/nope.yaml")"
check "P2 malformed config is rejected" "5" "$(scan_exit "$CONFIGS/malformed.yaml")"

python3 "$SCRIPTS/policy_scan.py" --config "$CONFIGS/comments.yaml" --check > "$TMP/check.log" 2>&1
check "P3 --check accepts a valid config" "0" "$?"

cat > "$TMP/bad-script.yaml" <<'YAML'
language:
  enabled: true
  forbid_scripts:
    - klingon
YAML
check "P4 unknown writing system is rejected" "5" "$(scan_exit "$TMP/bad-script.yaml")"

cat > "$TMP/bad-marker.yaml" <<'YAML'
comments:
  enabled: true
  forbid_markers:
    - angle_bracket
YAML
check "P5 unknown comment marker is rejected" "5" "$(scan_exit "$TMP/bad-marker.yaml")"

check "P33 a policy file that parses to nothing is rejected" "4" "$(scan_exit "$CONFIGS/empty.yaml")"

empty_include="$(scan_output "$CONFIGS/empty-include.yaml" | grep -oE 'files scanned: [0-9]+' | grep -oE '[0-9]+')"
if [ -n "$empty_include" ] && [ "$empty_include" -gt 0 ]; then
  ok "P34 an include key present but empty still scans the tree ($empty_include files)"
else
  echo "        files scanned: ${empty_include:-none} - an empty include must not silently scan nothing"
  bad "P34 an include key present but empty still scans the tree"
fi

echo ""
echo "--- rule: comments (a lexer, not a grep) ---"

expect_found  "P6 line comment in javascript is a finding"    "$CONFIGS/comments.yaml" 'dirty/comments\.js:2:[0-9]* \[comments\] slash_line'
expect_found  "P7 block comment in javascript is a finding"   "$CONFIGS/comments.yaml" 'dirty/comments\.js:6:[0-9]* \[comments\] slash_block'
expect_found  "P8 block comment in css is a finding"          "$CONFIGS/comments.yaml" 'dirty/block\.css:2:[0-9]* \[comments\] slash_block'
expect_absent "P9 url, regex literal and division are not comments" "$CONFIGS/comments.yaml" 'clean/tricky\.js'
expect_absent "P10 two slashes are not a css comment"         "$CONFIGS/comments.yaml" 'clean/plain\.css'
check         "P11 nested rust block comment is one finding" "1" "$(count_matches "$CONFIGS/comments.yaml" 'dirty/nested\.rs')"
expect_absent "P12 python floor division is not a slash comment" "$CONFIGS/comments.yaml" 'floor_division\.py'
expect_absent "P13 hash comment is inert when only slash markers are forbidden" "$CONFIGS/comments.yaml" 'hash_comments\.py'
expect_found  "P14 hash comment is a finding when hash is forbidden" "$CONFIGS/hash-comments.yaml" 'hash_comments\.py:5:[0-9]* \[comments\] hash'
check         "P15 clean source tree passes" "0" "$(scan_exit "$CONFIGS/all-clean.yaml")"
check         "P16 dirty source tree fails"  "1" "$(scan_exit "$CONFIGS/all-dirty.yaml")"

echo ""
echo "--- rule: emoji ---"

expect_found  "P17 pictograph is a finding"              "$CONFIGS/emoji.yaml" 'U+1F680'
expect_found  "P18 emoji variation selector is a finding" "$CONFIGS/emoji.yaml" 'U+FE0F'
expect_found  "P19 dingbat is a finding"                 "$CONFIGS/emoji.yaml" 'U+2705'
expect_absent "P20 clean tree reports no emoji findings" "$CONFIGS/all-clean.yaml" '\[emoji\]'

echo ""
echo "--- rule: language ---"

check         "P21 four forbidden writing systems are detected" "4" "$(scan_output "$CONFIGS/language.yaml" | grep -oE 'writing system `[a-z]+`' | sort -u | wc -l | tr -d ' ')"
check         "P22 scope exclusion exempts a documented fixture" "0" "$(scan_exit "$CONFIGS/language-exempt.yaml")"
check         "P23 unexempted fixtures still fail" "1" "$(scan_exit "$CONFIGS/language.yaml")"

echo ""
echo "--- rule: branding ---"

check         "P24 prohibited string is reported case insensitively" "2" "$(count_matches "$CONFIGS/branding.yaml" 'prohibited string `ObsiFox`')"
expect_absent "P25 allow_paths keeps attribution legal" "$CONFIGS/branding.yaml" 'branding-allowed'

echo ""
echo "--- scanner shell contract and the G6 gate ---"

mkdir -p "$TMP/workspace/scripts" "$TMP/workspace/.eng" "$TMP/workspace/src"
cp "$SCRIPTS"/*.sh "$SCRIPTS"/*.py "$TMP/workspace/scripts/"
chmod +x "$TMP/workspace/scripts/"*.sh
printf '%s\n' 'export function resolve(total, count) {' '  // a comment the policy forbids' '  return total / count;' '}' > "$TMP/workspace/src/resolver.js"

cat > "$TMP/workspace/.eng/policy.yaml" <<'YAML'
scope:
  include:
    - "src/**"
  exclude:
    - "**/.git/**"
comments:
  enabled: true
  forbid_markers:
    - slash_line
    - slash_block
emoji:
  enabled: true
language:
  enabled: true
branding:
  enabled: false
YAML

cd "$TMP/workspace"

./scripts/policy_scan.sh --config .eng/policy.yaml --out .eng/artifacts/policy_scan.log > "$TMP/shell.log" 2>&1
shell_exit=$?
check "P26 policy_scan.sh propagates the violation exit code" "1" "$shell_exit"

if grep -q '^EXIT_CODE=1$' .eng/artifacts/policy_scan.log; then ok "P27 the log carries EXIT_CODE for get_exit"; else bad "P27 the log carries EXIT_CODE for get_exit"; fi
if grep -q 'RESULT: FAIL' .eng/artifacts/policy_scan.log; then ok "P28 the log carries RESULT for the gate"; else bad "P28 the log carries RESULT for the gate"; fi

./scripts/gate_check.sh G6_Policy > "$TMP/gate_fail.log" 2>&1
check "P29 G6_Policy FAILs on a violating tree" "1" "$?"

cat > .eng/policy.yaml <<'YAML'
scope:
  include:
    - "nothing-in-scope/**"
  exclude:
    - "**/.git/**"
comments:
  enabled: true
  forbid_markers:
    - slash_line
    - slash_block
emoji:
  enabled: true
language:
  enabled: true
branding:
  enabled: false
YAML

./scripts/gate_check.sh G6_Policy > "$TMP/gate_pass.log" 2>&1
check "P30 G6_Policy PASSes on a clean tree" "0" "$?"

rm -f .eng/policy.yaml
./scripts/gate_check.sh G6_Policy > "$TMP/gate_na.log" 2>&1
check "P31 G6_Policy is NOT APPLICABLE without a policy file" "3" "$?"

cd "$REPO_ROOT"
./scripts/gate_check.sh G6_Policy > "$TMP/gate_repo.log" 2>&1
check "P32 this repository has no policy file so the gate is inert here" "3" "$?"

echo ""
echo "=== SUMMARY ==="
echo "PASS: $PASS"
echo "FAIL: $FAIL"
if [ "$FAIL" -eq 0 ]; then
  echo "RESULT: ALL POLICY SCAN TESTS PASS ($PASS)"
  exit 0
else
  echo "RESULT: SOME FAIL"
  exit 1
fi
