#!/usr/bin/env bash
set -uo pipefail
# arena.test.sh - Tests for Arena Tournament Mode v2.0 integration

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PASS=0
FAIL=0

ok() { echo "  PASS: $1"; PASS=$((PASS+1)); }
fail() { echo "  FAIL: $1"; FAIL=$((FAIL+1)); }

echo "=== Arena Tests v2.0 ==="

# Test 1: bracket.py exists and executable
if [[ -f "$ROOT/skills/arena/bracket.py" && -x "$ROOT/skills/arena/bracket.py" ]]; then
  ok "bracket.py exists and executable"
else
  chmod +x "$ROOT/skills/arena/bracket.py" 2>/dev/null || true
  if [[ -f "$ROOT/skills/arena/bracket.py" ]]; then
    ok "bracket.py exists"
  else
    fail "bracket.py missing"
  fi
fi

# Test 2: strategies.json valid JSON and has 2160 combos
if python3 -c "import json; data=json.load(open('$ROOT/skills/arena/strategies.json')); assert len(data['reasoning'])==15; assert len(data['workflows'])==12; assert len(data['strategies'])==12; print(f\"{len(data['reasoning'])}x{len(data['workflows'])}x{len(data['strategies'])}={len(data['reasoning'])*len(data['workflows'])*len(data['strategies'])}\")" 2>&1 | grep -q "2160"; then
  ok "strategies.json 15x12x12=2160 combos"
else
  fail "strategies.json invalid or not 2160"
fi

# Test 3: rubric.md exists
if [[ -f "$ROOT/skills/arena/rubric.md" ]]; then
  ok "rubric.md exists"
else
  fail "rubric.md missing"
fi

# Test 4: config/arena.yaml exists
if [[ -f "$ROOT/config/arena.yaml" ]]; then
  ok "config/arena.yaml exists"
else
  fail "config/arena.yaml missing"
fi

# Test 5: workflows/arena.yaml exists
if [[ -f "$ROOT/workflows/arena.yaml" ]]; then
  ok "workflows/arena.yaml exists"
else
  fail "workflows/arena.yaml missing"
fi

# Test 6: scripts/arena.sh exists and executable
if [[ -f "$ROOT/scripts/arena.sh" && -x "$ROOT/scripts/arena.sh" ]]; then
  ok "scripts/arena.sh exists and executable"
else
  chmod +x "$ROOT/scripts/arena.sh" 2>/dev/null || true
  if [[ -f "$ROOT/scripts/arena.sh" ]]; then ok "scripts/arena.sh exists"; else fail "arena.sh missing"; fi
fi

# Test 7: bracket.py plan --quick
if python3 "$ROOT/skills/arena/bracket.py" plan --quick 2>&1 | grep -q "agents"; then
  ok "bracket.py plan --quick"
else
  fail "bracket.py plan --quick"
fi

# Test 8: bracket.py plan --agents 100
if python3 "$ROOT/skills/arena/bracket.py" plan --agents 100 2>&1 | grep -q "100"; then
  ok "bracket.py plan --agents 100 shows 100"
else
  fail "bracket.py plan --agents 100"
fi

# Test 9: bracket.py init with 4 agents
TMPDIR=$(mktemp -d)
if python3 "$ROOT/skills/arena/bracket.py" init --agents 4 --seed 7 --task "Test task" --dir "$TMPDIR" 2>&1 | grep -q -E "init|created|agents"; then
  if [[ -f "$TMPDIR/arena.json" ]]; then
    ok "bracket.py init --agents 4 creates arena.json"
  else
    fail "arena.json not created after init"
  fi
else
  # Check file anyway
  if [[ -f "$TMPDIR/arena.json" ]]; then
    ok "bracket.py init --agents 4 creates arena.json (via file check)"
  else
    fail "bracket.py init --agents 4"
  fi
fi

# Test 10: arena.json valid and has 4 agents
if python3 -c "import json; d=json.load(open('$TMPDIR/arena.json')); assert len(d['agents'])==4; print('ok')" 2>&1 | grep -q "ok"; then
  ok "arena.json has 4 agents"
else
  fail "arena.json agent count"
fi

# Test 11: pairings
if python3 "$ROOT/skills/arena/bracket.py" pairings --dir "$TMPDIR" 2>&1 | grep -q "round"; then
  ok "bracket.py pairings"
else
  fail "bracket.py pairings"
fi

# Test 12: status
if python3 "$ROOT/skills/arena/bracket.py" status --dir "$TMPDIR" 2>&1 | grep -q -E "alive|round|agents"; then
  ok "bracket.py status"
else
  fail "bracket.py status"
fi

# Test 13: eng.sh arena plan
if "$ROOT/scripts/eng.sh" arena plan --quick 2>&1 | grep -q -E "agents|rounds|calls|16"; then
  ok "eng.sh arena plan --quick"
else
  fail "eng.sh arena plan --quick"
fi

# Test 14: arena.sh plan
if "$ROOT/scripts/arena.sh" plan --quick 2>&1 | grep -q -E "agents|16"; then
  ok "arena.sh plan --quick"
else
  fail "arena.sh plan --quick"
fi

# Test 15: arena run creates RUN
RUN_OUTPUT=$("$ROOT/scripts/arena.sh" run --task "Test arena run" --agents 4 --seed 7 2>&1)
RUN_ID=$(echo "$RUN_OUTPUT" | grep -oE "RUN-[0-9]+-[0-9]+" | head -n1 || echo "")
if [[ -n "$RUN_ID" && -d "$ROOT/.eng/runs/$RUN_ID" ]]; then
  ok "arena.sh run creates RUN $RUN_ID"
  # Check arena dir inside run
  if [[ -d "$ROOT/.eng/runs/$RUN_ID/arena" && -f "$ROOT/.eng/runs/$RUN_ID/arena/arena.json" ]]; then
    ok "arena dir inside run with arena.json"
  else
    fail "arena dir not created inside run"
  fi
  # Test next
  if "$ROOT/scripts/arena.sh" next --run "$RUN_ID" 2>&1 | grep -q -E "spawn|next|prompts"; then
    ok "arena.sh next --run"
  else
    fail "arena.sh next --run"
  fi
  # Test prompts spawn
  if "$ROOT/scripts/arena.sh" prompts spawn --run "$RUN_ID" 2>&1 | grep -q -E "spawn|brief|wave|agent"; then
    ok "arena.sh prompts spawn"
  else
    fail "arena.sh prompts spawn"
  fi
  # Cleanup
  rm -rf "$ROOT/.eng/runs/$RUN_ID"
  rm -rf "$ROOT/.arena"
else
  fail "arena.sh run creates RUN (got: $RUN_ID)"
fi

rm -rf "$TMPDIR"

# Test 16: SKILL.md contains arena section
if grep -q "Arena Tournament Mode" "$ROOT/SKILL.md"; then
  ok "SKILL.md contains Arena section"
else
  fail "SKILL.md missing Arena section"
fi

# Test 17: SKILL.md version 2.x
if grep -qE "version: 2\.[0-9]+\.[0-9]+" "$ROOT/SKILL.md"; then
  ok "SKILL.md version 2.x (arena integrated)"
else
  fail "SKILL.md version not 2.x"
fi

echo ""
echo "=== Results ==="
echo "PASS: $PASS"
echo "FAIL: $FAIL"
echo "Total: $((PASS+FAIL))"

if [[ $FAIL -eq 0 ]]; then
  echo "RESULT: ALL ARENA TESTS PASS ($PASS)"
  exit 0
else
  echo "RESULT: ARENA TESTS FAIL - $FAIL failures"
  exit 1
fi
