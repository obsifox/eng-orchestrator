#!/usr/bin/env bash
# project_profile.test.sh - Project profile + PHP detection + G5 + secret allow list (v1.2)
# 16 asserts. Everything here is executed, nothing is claimed.
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SCRIPTS="$REPO_ROOT/scripts"

PASS=0
FAIL=0
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

ok()   { echo "  ✅ $1 PASS"; PASS=$((PASS+1)); }
bad()  { echo "  ❌ $1 FAIL"; FAIL=$((FAIL+1)); }
check(){ if [ "$2" = "$3" ]; then ok "$1"; else echo "     expected=$2 got=$3"; bad "$1"; fi; }

echo "=== PROJECT PROFILE TESTS v1.2 ==="

# ------------------------------------------------------------------ fixtures
php_project="$TMP/php-project"
mkdir -p "$php_project/.eng" "$php_project/tests" "$php_project/bin" "$php_project/tools"
cat > "$php_project/.eng/project.yaml" <<'YAML'
name: Fixture PHP
kind: wordpress-plugin
commands:
  build: php bin/build.php --out=dist
  test: php tests/run.php
  lint: php bin/lint.php
gates:
  extras:
    - name: always_ok
      command: bash -c "exit 0"
      required: true
    - name: always_fail_optional
      command: bash -c "exit 7"
      required: false
secret_scan:
  allow: .eng/secret_scan.allow
YAML
printf 'exit 0\n' > "$php_project/tests/run.php"

# A profile whose required extra fails, and one with no extras at all.
mkdir -p "$TMP/strict/.eng"
sed 's/exit 0/exit 4/' "$php_project/.eng/project.yaml" > "$TMP/strict/.eng/project.yaml"
mkdir -p "$TMP/noextras/.eng"
printf 'name: No extras\ncommands:\n  test: true\n' > "$TMP/noextras/.eng/project.yaml"

# Malformed: a tab-indented line is outside the supported subset.
mkdir -p "$TMP/bad/.eng"
printf 'name: Bad\n\tcommands: oops\n' > "$TMP/bad/.eng/project.yaml"

# Empty profile.
mkdir -p "$TMP/empty/.eng"
printf '# only a comment\n' > "$TMP/empty/.eng/project.yaml"

# Node project for the backward-compatibility check.
mkdir -p "$TMP/node"
printf '{"name":"n","scripts":{"build":"echo b","test":"echo t"}}\n' > "$TMP/node/package.json"

# ------------------------------------------------------------------ profile parsing
echo "--- P1: profile parses ---"
out=$("$SCRIPTS/project_profile.sh" --file "$php_project/.eng/project.yaml" --check 2>&1); ec=$?
if [ $ec -eq 0 ] && echo "$out" | grep -q "Fixture PHP"; then ok "P1 parse ok"; else echo "     $out"; bad "P1 parse"; fi

echo "--- P2: malformed profile is rejected loudly ---"
"$SCRIPTS/project_profile.sh" --file "$TMP/bad/.eng/project.yaml" --check >/dev/null 2>&1; check "P2 malformed -> 5" 5 $?

echo "--- P3: empty profile exits 4 ---"
"$SCRIPTS/project_profile.sh" --file "$TMP/empty/.eng/project.yaml" --check >/dev/null 2>&1; check "P3 empty -> 4" 4 $?

echo "--- P4: no profile exits 3 (NOT APPLICABLE) ---"
"$SCRIPTS/project_profile.sh" --file "$TMP/none/.eng/project.yaml" --check >/dev/null 2>&1; check "P4 missing -> 3" 3 $?

echo "--- P5: gates are printed as name|command|required ---"
gates=$("$SCRIPTS/project_profile.sh" --file "$php_project/.eng/project.yaml" --gates)
if echo "$gates" | grep -q "^always_ok|.*|true$" && echo "$gates" | grep -q "^always_fail_optional|.*|false$"; then
  ok "P5 gates listing"
else
  echo "     $gates"; bad "P5 gates listing"
fi

# ------------------------------------------------------------------ detection order
echo "--- P6: the profile wins over heuristics ---"
detected=$(cd "$php_project" && bash -c 'source "'"$SCRIPTS"'/lib_run.sh"; detect_cmds; echo "$BUILD_CMD|$TEST_CMD|$LINT_CMD"')
check "P6 profile commands" "php bin/build.php --out=dist|php tests/run.php|php bin/lint.php" "$detected"

echo "--- P7: a PHP tree without a profile detects tests/run.php (not pytest) ---"
mkdir -p "$TMP/php-plain/tests" "$TMP/php-plain/.eng"
printf 'exit 0\n' > "$TMP/php-plain/tests/run.php"
# .eng exists so the profile probe runs, but there is no profile file.
detected=$(cd "$TMP/php-plain" && bash -c 'source "'"$SCRIPTS"'/lib_run.sh"; detect_cmds; echo "$TEST_CMD"')
check "P7 php fallback" "php tests/run.php" "$detected"

echo "--- P8: without .eng at all, behaviour is unchanged ---"
detected=$(cd "$TMP/php-plain" && rm -rf .eng && bash -c 'source "'"$SCRIPTS"'/lib_run.sh"; detect_cmds; echo "$TEST_CMD"')
check "P8 php fallback without .eng" "php tests/run.php" "$detected"

echo "--- P9: a Node project keeps npm detection ---"
detected=$(cd "$TMP/node" && bash -c 'source "'"$SCRIPTS"'/lib_run.sh"; detect_cmds; echo "$BUILD_CMD|$TEST_CMD"')
check "P9 npm detection" "npm run build|npm test" "$detected"

# ------------------------------------------------------------------ G5 gate
echo "--- P10: G5 with a passing required extra -> exit 0 ---"
(cd "$php_project" && "$SCRIPTS/gate_check.sh" G5_Project >/dev/null 2>&1); check "P10 G5 pass" 0 $?

echo "--- P11: G5 with a failing required extra -> exit 1 ---"
(cd "$TMP/strict" && "$SCRIPTS/gate_check.sh" G5_Project >/dev/null 2>&1); check "P11 G5 fail" 1 $?

echo "--- P12: G5 with no extras declared -> exit 3 ---"
(cd "$TMP/noextras" && "$SCRIPTS/gate_check.sh" G5_Project >/dev/null 2>&1); check "P12 G5 not applicable" 3 $?

echo "--- P13: G5 --no-run reads the logs instead of re-running ---"
(cd "$php_project" && rm -rf .eng/artifacts && "$SCRIPTS/gate_check.sh" G5_Project --no-run >/dev/null 2>&1); check "P13 G5 --no-run without logs" 2 $?

echo "--- P14: an optional failure does not fail G5 ---"
(cd "$php_project" && "$SCRIPTS/gate_check.sh" G5_Project >/dev/null 2>&1)
optional_code=$(grep -c 'EXIT_CODE=7' "$php_project/.eng/artifacts/profile_always_fail_optional.log" 2>/dev/null || echo 0)
check "P14 optional ran and was tolerated" 1 "$optional_code"

# ------------------------------------------------------------------ secret allow list
secret_dir="$TMP/secrets"
mkdir -p "$secret_dir/.eng" "$secret_dir/tools"
cat > "$secret_dir/.eng/secret_scan.allow" <<'ALLOW'
github_pat_ | tools/publisher.sh | greps the pattern; never contains a value
ALLOW
printf 'grep -o "github_pat_[A-Za-z0-9_]*" "$1"\nexit 0\n' > "$secret_dir/tools/publisher.sh"

echo "--- P15: a documented occurrence passes the scan ---"
(cd "$secret_dir" && "$SCRIPTS/secret_scan.sh" --path . --out /tmp/pp-scan1.log >/dev/null 2>&1); check "P15 documented occurrence" 0 $?

echo "--- P16: the same pattern in an undocumented file fails ---"
printf 'gh_pat = "github_pat_11ABCDEFG0123456789abcdefghij"\n' > "$secret_dir/leak.md"
(cd "$secret_dir" && "$SCRIPTS/secret_scan.sh" --path . --out /tmp/pp-scan2.log >/dev/null 2>&1); check "P16 undocumented occurrence" 1 $?

echo "--- P17: an allowance without a reason is ignored ---"
rm -f "$secret_dir/leak.md"
printf 'github_pat_ | tools/publisher.sh |\n' > "$secret_dir/.eng/secret_scan.allow"
(cd "$secret_dir" && "$SCRIPTS/secret_scan.sh" --path . --out /tmp/pp-scan3.log >/dev/null 2>&1); check "P17 reasonless allowance ignored" 1 $?

echo ""
echo "=== RESULT ==="
echo "PASS: $PASS"
echo "FAIL: $FAIL"

if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
exit 0
