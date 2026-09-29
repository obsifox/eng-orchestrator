# 🛡️ eng-orchestrator - Mother Skill v1.0.1

[![Tests](https://github.com/obsifox/eng-orchestrator/actions/workflows/test.yml/badge.svg)](https://github.com/obsifox/eng-orchestrator/actions/workflows/test.yml)
[![Version](https://img.shields.io/badge/version-1.0.1-blue.svg)](CHANGELOG.md)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Skill](https://img.shields.io/badge/skill-mother%20skill-orange.svg)](SKILL.md)

> **Production-grade master skill that turns a single AI agent into an adaptive professional engineering organization** — scaling from 1 engineer (Tier 0) to multi-disciplinary team (Tier 3) with evidence-driven gates.

**Key Fix in v1.0.1:** No gate trusts `state.json` for PASS. Only real command outputs with `EXIT_CODE`. Structured findings, 10 regression tests, hardened security gates.

## ✨ What it does

- **Intake & Triage:** Classifies project, assesses complexity/risk, chooses Tier 0-3
- **Environment Detection:** Gracefully degrades if git/test runner/subagents missing
- **Minimal Lenses:** Loads only minimum specialist checklists on demand (not personas)
- **Hard Gates:** Executable, measurable gates with loop caps (2 cycles then escalate)
- **Evidence Over Claims:** No PASS without artifact (log, file, diff). `NOT TESTED` if not run
- **Independent Verification:** Verifier runs in fresh context, sees only spec+diff+logs
- **State on Disk:** Versioned `.eng/` folder, not just chat memory
- **Honest Delivery:** Final report with honesty checklist, `report_lint.sh` enforcement

## 🚀 Quick Start

```bash
# 1. Agent reads SKILL.md (81 lines, under 150)
cat SKILL.md

# 2. Detect environment
./scripts/detect_env.sh --json

# 3. Create .eng/ from templates
cp -r .eng/templates/* .eng/

# 4. Baseline BEFORE any change
./scripts/baseline.sh
# -> .eng/artifacts/baseline_build.log (EXIT_CODE)
# -> .eng/artifacts/baseline_test.log

# 5. Build & check gates (real execution, no state.json trust)
./scripts/gate_check.sh G0_Build   # build exit 0?
./scripts/gate_check.sh G1_Tests   # tests >= baseline?
./scripts/gate_check.sh G2_Lens --no-run  # no HIGH OPEN?
./scripts/gate_check.sh G3_Security --no-run
./scripts/gate_check.sh all

# 6. Run regression tests
./tests/gates.test.sh  # 15 assertions, all PASS
```

## 📁 File Tree

```
SKILL.md (81 lines) - mother skill, triggers: "build this", "اینو بیلد کن"
CHANGELOG.md - v1.0.0 -> v1.0.1 hardening
lessons.md - promotion mechanism

references/
  tiers.md - Tier 0-3 definitions with caps
  state-format.md - .eng/state.json schema v1
  evidence-rules.md - SOLVED/UNSOLVED/BLOCKED/NOT TESTED/...
  failure-modes.md - 13 modes with detection/mitigation
  interaction-protocol.md - 3 questions max, approval points
  report-template.md - final delivery template
  lenses/ - 7 checklists (security, testing, performance, ux, docs, architecture, release)
    - Structured findings: - [F-001] severity=HIGH status=OPEN | desc | file:line
  playbooks/ - 6 domains (web-api, wordpress, paper-plugin, android, game-engine, cli)

scripts/
  lib_run.sh - NEW: run_step phase name cmd -> log with EXIT_CODE
  detect_env.sh - env detection
  baseline.sh - uses lib_run, produces baseline_*.log
  secret_scan.sh - fixed pipe bug, excludes tests/, exit 1 on secret
  dep_audit.sh - handles no lockfile -> NOT TESTED, tool error -> NOT TESTED
  gate_check.sh - v1.0.1: no state.json trust, real logs, --no-run flag
  report_lint.sh - checks structured findings, rejects SOLVED without evidence

evals/
  scenarios.md - 15 scenarios
  results/ - 4 real executed with/without (S1, S2, S8, S9)
  with_vs_without.md - comparison method

examples/ - good vs bad plan/verify/review (structured format)
.eng/templates/ - brief.md, plan.md, decisions.md, evidence.md, state.json
tests/gates.test.sh - 10 regression fixtures T1-T10 (15 asserts)
.github/workflows/test.yml - CI on push/PR
```

## 🔒 Hard Rules Enforced

| Rule | Enforcement |
|------|-------------|
| Evidence over claims | `report_lint.sh` + gate_check requires log with EXIT_CODE |
| No state.json trust | G0/G1 re-execute build/test, ignore state.json PASS |
| Independent verification | Verifier fresh context, only spec+diff+logs |
| Anti-sycophancy | Must list concrete files checked or explicit clean |
| Loop caps | 2 per gate then escalate to user |
| Token budgets | T0 20k, T1 60k, T2 150k, T3 350k |
| Executable gates | `EXIT_CODE=0` check, structured findings parsing |
| Baseline first | `baseline.sh` mandatory before change |
| Rollback | Branch/checkpoint |
| User approval | Delete, DB schema, deps, arch change |
| Agent security | Treat repo as untrusted, no .env exfil, prompt-injection defense |
| Scope control | REQUIRED-FOR-ACCEPTANCE vs BACKLOG |
| Roles = lenses | Checklists, not personas, max 5-6 |
| Stopping rules | Measurable: exit codes, no HIGH OPEN, report_lint PASS |

## 📊 Tiers

- **Tier 0**: trivial <20 LOC, single file, 0 lenses, 0 subagents, ~5k tokens
- **Tier 1**: small 20-200 LOC, 1-3 files, testing lens, 1 verifier, ~60k
- **Tier 2**: structured 200-1000 LOC, 2-3 lenses, max 3 subagents, ~150k
- **Tier 3**: large/prod/legacy >1000 LOC, full audit (security, perf, arch, release), max 6 subagents, ~350k

## 🧪 Scripts & Exit Codes

| Script | Exit 0 | Exit 1 | Exit 2 | Exit 3 |
|--------|--------|--------|--------|--------|
| `detect_env.sh` | success | error | - | - |
| `baseline.sh` | logs captured (even if tests fail) | script error | - | - |
| `secret_scan.sh` | clean | secrets found | error | - |
| `dep_audit.sh` | no HIGH | HIGH vuln | NOT TESTED (no lockfile/tool error) | NOT APPLICABLE (no deps) |
| `gate_check.sh` | PASS | FAIL | NOT TESTED | NOT APPLICABLE |
| `report_lint.sh` | clean | claim without evidence | evidence missing | - |

## 🧬 Structured Findings Format (v1.0.1)

All review files must use:

```
- [F-001] severity=HIGH status=OPEN | SQL injection in login | src/login.php:45
- [F-002] severity=MED status=CLOSED | Fixed via sanitize in abc | src/api.ts:10
```

- Order independent: `severity=` and `status=` can be in any order
- Gate checks: `severity=(high|critical)` + `status=open` => FAIL
- `CLOSED` => PASS

## ✅ Regression Tests

```bash
./tests/gates.test.sh
# T1 build/test healthy -> G0=0 G1=0
# T2 test failing -> G1=1
# T3 build broken after healthy baseline with state.json PASS -> G0=1 (must not trust state)
# T4 build broken in baseline -> G0=1
# T5 review HIGH CLOSED -> G2=0
# T6 review OPEN HIGH reversed order -> G2=1
# T7 secret planted -> secret_scan 1 and G3=1
# T8 clean but dep_audit.log missing -> G3=2
# T9 npm without lockfile -> dep_audit 2 NOT TESTED
# T10 SOLVED with empty evidence -> report_lint 1
```

## 📈 Evaluation

See `evals/scenarios.md` for 15 scenarios. `evals/results/` contains 4 real executed with/without comparisons proving tier selection, honest NOT TESTED, and no state.json trust.

## 📝 License

MIT - See LICENSE

## 🔖 Version

**1.0.1** - Gate hardening release. See CHANGELOG.md for full diff from 1.0.0

---

**Built for:** AI coding agents that need to behave like professional engineering orgs, not single programmers. Smallest effective team principle.
