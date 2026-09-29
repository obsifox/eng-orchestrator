#!/usr/bin/env bash
# playbook.test.sh - Playbook composition tests v1.1
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

PASS=0
FAIL=0

echo "=== PLAYBOOK TESTS v1.1 ==="

# Test 1: Compose feature + web
echo "--- P1: Compose feature + web ---"
./scripts/playbook_engine.sh compose --type feature --domain web --tier T2 --out /tmp/plan_test.md >/dev/null 2>&1
if [ -f /tmp/plan_test.md ] && grep -q "feature" /tmp/plan_test.md; then
  echo "  ✅ P1 compose feature+web PASS"
  PASS=$((PASS+1))
else
  echo "  ❌ P1 FAIL"
  FAIL=$((FAIL+1))
fi

# Test 2: Compose bug-fix + wordpress + security high
echo "--- P2: Compose bug-fix + wordpress + security high + T3 ---"
./scripts/playbook_engine.sh compose --type bug-fix --domain wordpress --risk "security:high" --tier T3 --out /tmp/plan_test2.md >/dev/null 2>&1
if [ -f /tmp/plan_test2.md ] && grep -q "security" /tmp/plan_test2.md; then
  echo "  ✅ P2 compose with risk overlay PASS"
  PASS=$((PASS+1))
else
  echo "  ❌ P2 FAIL"
  FAIL=$((FAIL+1))
fi

# Test 3: List workflows
echo "--- P3: List workflows ---"
out=$(./scripts/playbook_engine.sh list 2>&1 || true)
if echo "$out" | grep -q "feature"; then
  echo "  ✅ P3 list workflows PASS"
  PASS=$((PASS+1))
else
  echo "  ❌ P3 FAIL (out: $out)"
  FAIL=$((FAIL+1))
fi

# Test 4: Preview mode no mutation
echo "--- P4: Preview no mutation ---"
BEFORE=$(git status --porcelain 2>/dev/null | wc -l)
./scripts/preview.sh --type feature --task "Add API" >/dev/null 2>&1
AFTER=$(git status --porcelain 2>/dev/null | wc -l)
if [ "$BEFORE" = "$AFTER" ]; then
  echo "  ✅ P4 preview no mutation PASS"
  PASS=$((PASS+1))
else
  echo "  ❌ P4 FAIL - preview mutated files"
  FAIL=$((FAIL+1))
fi

# Test 5: Preview shows tier, agents, gates
echo "--- P5: Preview shows tier/agents/gates ---"
OUT=$(./scripts/preview.sh --type feature --task "Build production SaaS platform with auth" 2>&1)
if echo "$OUT" | grep -q "Tier:" && echo "$OUT" | grep -q "Agents" && echo "$OUT" | grep -q "Gates"; then
  echo "  ✅ P5 preview output PASS"
  PASS=$((PASS+1))
else
  echo "  ❌ P5 FAIL"
  FAIL=$((FAIL+1))
fi

# Test 6: Workflow file exists
echo "--- P6: Workflow files exist ---"
if [ -f "$REPO_ROOT/workflows/feature.yaml" ] && [ -f "$REPO_ROOT/workflows/security.yaml" ]; then
  echo "  ✅ P6 workflows exist PASS"
  PASS=$((PASS+1))
else
  echo "  ❌ P6 FAIL"
  FAIL=$((FAIL+1))
fi

# Test 7: Domain overlay exists
echo "--- P7: Domain overlays exist ---"
if [ -f "$REPO_ROOT/domains/wordpress.yaml" ] && [ -f "$REPO_ROOT/domains/backend.yaml" ]; then
  echo "  ✅ P7 domains exist PASS"
  PASS=$((PASS+1))
else
  echo "  ❌ P7 FAIL"
  FAIL=$((FAIL+1))
fi

rm -f /tmp/plan_test.md /tmp/plan_test2.md

echo ""
echo "=== SUMMARY ==="
echo "PASS: $PASS"
echo "FAIL: $FAIL"
if [ $FAIL -eq 0 ]; then
  echo "RESULT: ALL PLAYBOOK TESTS PASS (7)"
  exit 0
else
  echo "RESULT: SOME FAIL"
  exit 1
fi
