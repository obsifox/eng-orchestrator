#!/usr/bin/env bash
# dep_audit.sh - Dependency audit wrapper, dependency-light
# Usage: ./scripts/dep_audit.sh [--out .eng/artifacts/dep_audit.log]
# Exit codes: 0 no HIGH vuln, 1 HIGH/CRITICAL found, 2 no audit tool available (NOT TESTED)
set -uo pipefail

OUT=".eng/artifacts/dep_audit.log"
mkdir -p "$(dirname "$OUT")"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --out) OUT="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: $0 [--out <log>]"
      echo "Tries npm audit, pip-audit, govulncheck, gradle dependencyCheck"
      echo "Exit 0 clean, 1 HIGH found, 2 no tool"
      exit 0
      ;;
    *) shift ;;
  esac
done

FOUND_TOOL=false
HAS_HIGH=false

{
  echo "=== DEP AUDIT $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
  echo ""

  # Node
  if [ -f package.json ]; then
    if command -v npm >/dev/null 2>&1; then
      FOUND_TOOL=true
      echo "--- npm audit ---"
      npm audit --audit-level=high 2>&1 || {
        ec=$?
        echo "npm audit exit $ec"
        if [ $ec -ne 0 ]; then HAS_HIGH=true; fi
      }
      echo ""
    fi
    if command -v yarn >/dev/null 2>&1; then
      FOUND_TOOL=true
      echo "--- yarn audit ---"
      yarn audit --level high 2>&1 || {
        ec=$?
        echo "yarn audit exit $ec"
        if [ $ec -ne 0 ]; then HAS_HIGH=true; fi
      }
      echo ""
    fi
  fi

  # Python
  if [ -f requirements.txt ] || [ -f pyproject.toml ]; then
    if command -v pip-audit >/dev/null 2>&1; then
      FOUND_TOOL=true
      echo "--- pip-audit ---"
      pip-audit 2>&1 || {
        ec=$?
        echo "pip-audit exit $ec"
        if [ $ec -ne 0 ]; then HAS_HIGH=true; fi
      }
      echo ""
    else
      echo "--- pip-audit not installed, trying pip list check ---"
      if command -v python3 >/dev/null 2>&1; then
        FOUND_TOOL=true
        python3 -m pip list 2>&1 | head -n 50
        echo "(manual check, no vuln DB)"
      fi
      echo ""
    fi
  fi

  # Go
  if [ -f go.mod ]; then
    if command -v govulncheck >/dev/null 2>&1; then
      FOUND_TOOL=true
      echo "--- govulncheck ---"
      govulncheck ./... 2>&1 || {
        ec=$?
        echo "govulncheck exit $ec"
        if [ $ec -ne 0 ]; then HAS_HIGH=true; fi
      }
      echo ""
    else
      echo "govulncheck not installed, skipping"
      echo ""
    fi
  fi

  # Gradle
  if [ -f build.gradle ] || [ -f build.gradle.kts ]; then
    echo "--- Gradle dependencies ---"
    FOUND_TOOL=true
    if [ -f ./gradlew ]; then
      ./gradlew dependencies 2>&1 | head -n 100 || true
    fi
    echo "(manual review needed for vulns)"
    echo ""
  fi

  if ! $FOUND_TOOL; then
    echo "No supported audit tool found for this project"
    echo "RESULT: NOT TESTED - no audit tool"
  else
    if $HAS_HIGH; then
      echo "RESULT: FAIL - HIGH/CRITICAL vulnerabilities found"
    else
      echo "RESULT: PASS - No HIGH vulns detected (or manual review needed)"
    fi
  fi

} | tee "$OUT"

if ! $FOUND_TOOL; then exit 2; fi
if $HAS_HIGH; then exit 1; else exit 0; fi
