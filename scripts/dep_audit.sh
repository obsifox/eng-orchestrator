#!/usr/bin/env bash
# dep_audit.sh - Dependency audit wrapper v1.0.1
# Usage: ./scripts/dep_audit.sh [--out .eng/artifacts/dep_audit.log]
# Exit codes: 0 no HIGH vuln, 1 HIGH/CRITICAL found, 2 NOT TESTED (no tool/lockfile/error), 3 NOT APPLICABLE (no deps)
set -uo pipefail

OUT=".eng/artifacts/dep_audit.log"
mkdir -p "$(dirname "$OUT")"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --out) OUT="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: $0 [--out <log>]"
      echo "Tries npm audit, pip-audit, govulncheck"
      echo "Exit 0 clean, 1 HIGH found, 2 NOT TESTED, 3 NOT APPLICABLE"
      exit 0
      ;;
    *) shift ;;
  esac
done

FOUND_TOOL=false
HAS_HIGH=false
NOT_TESTED_REASON=""
NOT_APPLICABLE=false

{
  echo "=== DEP AUDIT $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
  echo ""

  # Check if project has any dependency manifest
  HAS_MANIFEST=false
  if [ -f package.json ] || [ -f requirements.txt ] || [ -f pyproject.toml ] || [ -f go.mod ] || [ -f build.gradle ] || [ -f build.gradle.kts ]; then
    HAS_MANIFEST=true
  fi

  if ! $HAS_MANIFEST; then
    echo "No dependency manifest found (package.json, requirements.txt, go.mod, etc)"
    echo "RESULT: NOT APPLICABLE - no dependencies to audit"
    exit 3
  fi

  # Node - handle lockfile missing per Fix 4b
  if [ -f package.json ]; then
    if [ ! -f package-lock.json ] && [ ! -f npm-shrinkwrap.json ] && [ ! -f yarn.lock ] && [ ! -f pnpm-lock.yaml ]; then
      echo "--- Node: package.json found but no lockfile ---"
      echo "RESULT: NOT TESTED - no lockfile (run: npm i --package-lock-only)"
      echo "This is NOT a vulnerability, but audit cannot run reliably without lockfile"
      exit 2
    fi

    if command -v npm >/dev/null 2>&1; then
      FOUND_TOOL=true
      echo "--- npm audit ---"
      # Use json to parse high+critical accurately
      if npm audit --json 2>&1 | tee /tmp/npm_audit.json; then
        # npm audit exit 0 means no vuln, but we parse json for safety
        if command -v python3 >/dev/null 2>&1; then
          python3 - << 'PY'
import json, sys
try:
    with open('/tmp/npm_audit.json') as f:
        data=json.load(f)
    vulns=data.get('metadata',{}).get('vulnerabilities',{})
    high=vulns.get('high',0)
    critical=vulns.get('critical',0)
    print(f"high={high} critical={critical}")
    if high+critical>0:
        sys.exit(1)
    sys.exit(0)
except Exception as e:
    print(f"Parse error: {e} -> tool error")
    sys.exit(2)
PY
          ec=$?
          if [ $ec -eq 1 ]; then HAS_HIGH=true; echo "HIGH/CRITICAL found"; 
          elif [ $ec -eq 2 ]; then NOT_TESTED_REASON="npm audit json parse error"; echo "Tool error"; 
          else echo "No HIGH/CRITICAL"; fi
        else
          # fallback: if npm audit exit non-zero, treat as vuln only if output contains high
          if grep -qi "high\|critical" /tmp/npm_audit.json; then HAS_HIGH=true; fi
        fi
      else
        ec=${PIPESTATUS[0]}
        # npm audit returns non-zero when vuln found, but also when error
        # Check if json file exists and parseable
        if [ ! -s /tmp/npm_audit.json ]; then
          NOT_TESTED_REASON="npm audit no output"
          echo "Audit tool error - no output"
        else
          if command -v python3 >/dev/null 2>&1; then
            python3 - << 'PY'
import json, sys
try:
    with open('/tmp/npm_audit.json') as f:
        data=json.load(f)
    vulns=data.get('metadata',{}).get('vulnerabilities',{})
    high=vulns.get('high',0)
    critical=vulns.get('critical',0)
    print(f"high={high} critical={critical}")
    sys.exit(1 if high+critical>0 else 0)
except:
    sys.exit(2)
PY
            ec2=$?
            if [ $ec2 -eq 1 ]; then HAS_HIGH=true
            elif [ $ec2 -eq 2 ]; then NOT_TESTED_REASON="parse error"; fi
          else
            HAS_HIGH=true
          fi
        fi
      fi
      echo ""
    fi
  fi

  # Python
  if [ -f requirements.txt ] || [ -f pyproject.toml ]; then
    if command -v pip-audit >/dev/null 2>&1; then
      FOUND_TOOL=true
      echo "--- pip-audit ---"
      if pip-audit --format=json -o /tmp/pip_audit.json 2>&1; then
        echo "pip-audit clean"
      else
        ec=$?
        if [ -s /tmp/pip_audit.json ]; then
          # parse if file has vulns
          if grep -q "vulnerabilities" /tmp/pip_audit.json; then HAS_HIGH=true; echo "Vulns found"; else echo "No output"; fi
        else
          NOT_TESTED_REASON="pip-audit error no json"
          echo "pip-audit error"
        fi
      fi
      cat /tmp/pip_audit.json 2>/dev/null || true
      echo ""
    else
      echo "--- pip-audit not installed, skipping (NOT TESTED for python) ---"
      # Don't mark as found tool if no audit tool
      echo ""
    fi
  fi

  # Go
  if [ -f go.mod ]; then
    if command -v govulncheck >/dev/null 2>&1; then
      FOUND_TOOL=true
      echo "--- govulncheck ---"
      if govulncheck ./... 2>&1 | tee /tmp/govuln.log; then
        echo "govulncheck clean"
      else
        if grep -qi "vulnerability" /tmp/govuln.log; then HAS_HIGH=true; fi
      fi
      echo ""
    fi
  fi

  if [ -n "$NOT_TESTED_REASON" ]; then
    echo "RESULT: NOT TESTED - audit tool error: $NOT_TESTED_REASON"
    exit 2
  fi

  if ! $FOUND_TOOL; then
    # If we had manifest but no tool, it's NOT TESTED not NOT APPLICABLE
    if $HAS_MANIFEST; then
      echo "No supported audit tool found for this project's manifest"
      echo "RESULT: NOT TESTED - no audit tool"
      exit 2
    else
      echo "RESULT: NOT APPLICABLE - no deps"
      exit 3
    fi
  fi

  if $HAS_HIGH; then
    echo "RESULT: FAIL - HIGH/CRITICAL vulnerabilities found"
    exit 1
  else
    echo "RESULT: PASS - No HIGH vulns detected"
    exit 0
  fi

} | tee "$OUT"
ec=${PIPESTATUS[0]}
# Capture exit from subshell block
# The block's exit is in $OUT but we need to propagate
# Re-parse result line
if grep -q "RESULT: FAIL" "$OUT"; then exit 1
elif grep -q "RESULT: NOT TESTED" "$OUT"; then exit 2
elif grep -q "RESULT: NOT APPLICABLE" "$OUT"; then exit 3
else exit 0
fi
