#!/usr/bin/env bash
# baseline.sh - Run existing build/tests before changes
# Usage: ./scripts/baseline.sh [--out .eng/artifacts/baseline.log]
# Exit codes: 0 success (even if tests fail, logs captured), 1 error in script itself
set -euo pipefail

OUT=".eng/artifacts/baseline.log"
mkdir -p "$(dirname "$OUT")"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --out) OUT="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: $0 [--out <log>]"
      echo "Runs detected build/test commands, records results for regression detection"
      echo "Exit 0 if script succeeded (test failures still 0), logs contain exit codes"
      exit 0
      ;;
    *) shift ;;
  esac
done

{
  echo "=== BASELINE RUN $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
  echo ""

  # Git status
  if command -v git >/dev/null 2>&1; then
    echo "--- git status ---"
    git status --porcelain || true
    echo ""
  fi

  # Node
  if [ -f package.json ]; then
    echo "--- package.json detected ---"
    if command -v npm >/dev/null 2>&1; then
      echo "Running npm run build if exists..."
      if grep -q '"build"' package.json; then
        npm run build 2>&1 || echo "BUILD_EXIT:$?"
      else
        echo "No build script"
      fi
      echo ""
      echo "Running npm test if exists..."
      if grep -q '"test"' package.json; then
        npm test 2>&1 || echo "TEST_EXIT:$?"
      else
        echo "No test script"
      fi
    fi
    echo ""
  fi

  # Python
  if [ -f pyproject.toml ] || [ -f requirements.txt ] || ls *.py >/dev/null 2>&1; then
    echo "--- Python detected ---"
    if command -v pytest >/dev/null 2>&1; then
      pytest -q 2>&1 || echo "PYTEST_EXIT:$?"
    elif command -v python3 >/dev/null 2>&1; then
      python3 -m unittest discover 2>&1 || echo "UNITTEST_EXIT:$?"
    fi
    echo ""
  fi

  # Go
  if ls *.go go.mod >/dev/null 2>&1; then
    echo "--- Go detected ---"
    go test ./... 2>&1 || echo "GO_TEST_EXIT:$?"
    echo ""
  fi

  # Java/Gradle
  if [ -f build.gradle ] || [ -f build.gradle.kts ] || [ -f ./gradlew ]; then
    echo "--- Gradle detected ---"
    if [ -f ./gradlew ]; then
      ./gradlew test 2>&1 || echo "GRADLE_TEST_EXIT:$?"
    else
      gradle test 2>&1 || echo "GRADLE_TEST_EXIT:$?"
    fi
    echo ""
  fi

  # Generic make
  if [ -f Makefile ]; then
    echo "--- Makefile detected ---"
    make test 2>&1 || echo "MAKE_TEST_EXIT:$?"
    echo ""
  fi

  echo "=== END BASELINE ==="

} | tee "$OUT"

# Always exit 0 unless script error, so evidence can be recorded even if tests fail
# Parse result for evidence.md helper
echo ""
echo "Baseline log saved to $OUT"
echo "Check for *_EXIT codes above for failures"

exit 0
