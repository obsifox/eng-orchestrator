# 🛡️ eng-orchestrator v2.1 - Control Plane + Project Profiles + Arena

[![Tests](https://github.com/obsifox/eng-orchestrator/actions/workflows/test.yml/badge.svg)](https://github.com/obsifox/eng-orchestrator/actions/workflows/test.yml)
[![Version](https://img.shields.io/badge/version-2.1.0-blue.svg)](CHANGELOG.md)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Skill](https://img.shields.io/badge/skill-control%20plane%20%2B%20arena%20%2B%20project-orange.svg)](SKILL.md)
[![Arena](https://img.shields.io/badge/arena-100%20agents%20tournament-red.svg)](skills/arena/)

> **Engineering Orchestration Control Plane + Project Profiles + Arena Tournament** — Turns AI agent into adaptive org with state machine, run manager, event log, agent contracts, permissions, model routing, playbook engine, project profiles, preview, recovery, receipt + when answers are bad, 100 sub-agents fight to the death with distinct strategy cards (15 reasoning x 12 workflows x 12 strategies = 2160 combos), attack/defend/judge bracket until one survives.

**v2.1.0 NEW (merged):** Arena tournament mode (bracket.py 1235 lines, strategies.json 2160 cards, rubric.md, config/arena.yaml, workflows/arena.yaml, scripts/arena.sh) + Project profiles (.eng/project.yaml, G5_Project gate, secret allow list, PHP detection) merged from v1.2.0/1.2.1 into v2.0 base. 151 eval PASS (108 unit + 43 simulated), 117 tests v1.2.

**v2.0.0:** Arena integrated - 100 agents 7 rounds 595 calls or quick 16 agents 4 rounds 91 calls, waves of 10, state on disk survives compaction, orchestrator never competes/judges.

**v1.2.1:** Dependency audit for PHP and nested manifests, timezone-aware timestamps, secret_scan allow file full reproduction.

**v1.2.0:** Project profiles (.eng/project.yaml) + PHP/Composer detection, G5_Project gate for project-defined extras, secret allow list, 29 new asserts, 117 total tests.

**v1.1.0:** State machine (17 states, 37 tests), Run Manager (RUN-xxx isolation), Event Log (23 types), Agent Contracts (6), Permission Matrix (21 tests), Model Routing (Tier != Model, 3 adapter.py), Playbook Engine (11 workflows + 15 domains), Preview no mutation, Recovery (8 tests), Worktree Isolation + cleanup, Receipt enrichment, Cost telemetry, Knowledge promotion, 88 tests + 122 eval PASS.

## ✨ What it does

- **Intake & Triage:** Classifies project, assesses complexity/risk, chooses Tier 0-3, detects project profile
- **Project Profiles (v1.2):** Repo declares build/test/lint in `.eng/project.yaml`, G5_Project gate runs extras, secret allow list
- **Arena Tournament (v2.0):** When answer bad or /arena, 16-100 agents compete with distinct cards, bracket until one survives
- **Environment Detection:** Gracefully degrades if git/test runner/subagents missing, PHP before pytest
- **Minimal Lenses:** Loads only minimum specialist checklists on demand (not personas)
- **Hard Gates:** Executable, measurable gates G0-G5 with loop caps (2 cycles then escalate)
- **Evidence Over Claims:** No PASS without artifact (log, file, diff). `NOT TESTED` if not run
- **Independent Verification:** Verifier runs in fresh context, sees only spec+diff+logs
- **State on Disk:** Versioned `.eng/` folder, not just chat memory
- **Honest Delivery:** Final report with honesty checklist, `report_lint.sh` enforcement

## 🚀 Quick Start

```bash
# 0. Declare how THIS project builds, tests and lints (v1.2)
cat .eng/project.yaml            # commands + gate extras + secret allow file
./scripts/project_profile.sh --check

# 1. Agent reads SKILL.md (v2.1)
cat SKILL.md

# 2. Preview without mutation
./scripts/eng.sh preview --type feature --task "Add auth"
./scripts/eng.sh arena plan --quick  # Arena preview: 16 agents, 4 rounds, 91 calls

# 3. Create isolated run
./scripts/eng.sh run create --type feature --domain web --tier T2 --task "Add API"
# -> RUN-2026-000001 with manifest.json, state.json, events.jsonl

# 4. Arena tournament (NEW v2.0)
./scripts/eng.sh arena run --task "Design auth system" --quick
# -> Creates RUN, init arena with 16 agents, guidance for next steps
./scripts/eng.sh arena next --run RUN-2026-000001
./scripts/eng.sh arena prompts spawn --run RUN-2026-000001
# Launch waves of 10 Agent tool calls, then next, loop until DONE
./scripts/eng.sh arena winner --run RUN-2026-000001
# -> Champion solution + why it won + card + rounds

# 5. State machine validation (deterministic)
./scripts/eng.sh state validate --from EXECUTION --to COMPLETED
# -> INVALID: Must go through VALIDATION, REVIEW, VERIFICATION

# 6. Baseline BEFORE any change
./scripts/baseline.sh
# -> .eng/artifacts/baseline_build.log (EXIT_CODE)

# 7. Build & check gates (real execution, no state.json trust)
./scripts/eng.sh gate G0_Build
./scripts/eng.sh gate G1_Tests
./scripts/eng.sh gate G5_Project
./scripts/eng.sh gate all

# 8. Run all tests (151 PASS v2.1)
./tests/gates.test.sh          # 15
./tests/state_machine.test.sh  # 37
./tests/permissions.test.sh    # 21
./tests/recovery.test.sh       # 8
./tests/playbook.test.sh       # 7
./tests/arena.test.sh          # 20 NEW v2.0
./tests/project_profile.test.sh # 9 NEW v1.2
./tests/dep_audit.test.sh      # ? NEW v1.2
```

## 📁 File Tree v2.1

```
SKILL.md (v2.1) - control plane + project profiles + arena, triggers: "build this", "اینو بیلد کن", "مسابقه بده", "arena"
CHANGELOG.md - v1.0.0 -> v1.1.0 -> v1.2.0 -> v1.2.1 -> v2.0.0 -> v2.1.0
LICENSE (MIT)

config/
  state_machine.yaml - 17 states, transitions
  permissions.yaml - least privilege matrix
  model_policy.yaml - Tier != Model, adapters
  arena.yaml - NEW v2.0: 100 agents, 16 quick, wave 10, rubric weights, triggers

agents/ (6 contracts)
  architect.yaml, worker.yaml, reviewer.yaml, security-reviewer.yaml, verifier.yaml, release-manager.yaml

workflows/ (12 types: 11 + arena NEW v2.0)
  feature, bug-fix, refactor, migration, performance, security, investigation, testing, release, documentation, incident, arena

domains/ (15 overlays)
  wordpress, woocommerce, android, minecraft, paper, web, backend, frontend, typescript, javascript, python, rust, game-development, cli, database

skills/arena/ NEW v2.0
  bracket.py (1235 lines) - tournament state machine
  strategies.json (2160 cards: 15 reasoning x 12 workflows x 12 strategies)
  rubric.md - correctness 30, completeness 25, specificity 15, robustness 20, clarity 10
  SKILL.md - original arena skill

adapters/
  generic (always), claude, codex, copilot - provider-independent with adapter.py

.eng/
  project.yaml - NEW v1.2: build/test/lint commands + gate extras + secret allow file
  secret_scan.allow - NEW v1.2: allow list with reasons
  templates/project.yaml - template
  templates/ - brief, plan, decisions, evidence, state.json
  knowledge/ - lessons/, failures/, decisions/, patterns/, regressions/

scripts/ (control plane + gates + arena + project)
  eng.sh - main CLI: preview, run, list, show, state, event, recover, worktree, receipt, registry, playbook, gate, arena NEW, project NEW, knowledge, cost
  arena.sh - NEW v2.0: wrapper around bracket.py with run_manager integration
  project_profile.py/.sh - NEW v1.2: validate .eng/project.yaml, detect_cmds, G5_Project
  state_machine.sh - list-states, validate, transition, current, history (37 tests)
  event_log.sh - append-only events.jsonl, 23 types + arena events
  run_manager.sh - create RUN-YYYY-XXXXXX with manifest, state, events, artifacts, checkpoints, receipt
  playbook_engine.sh - compose base+domain+risk+tier
  preview.sh - eng preview, no mutation + arena plan
  recovery.sh - detect, inspect, reconcile, recover, resume (8 tests) + arena resume via next
  worktree.sh - isolated worktree per run + cleanup --older-than
  receipt.sh - receipt.json generation with workflow/domain/risk/cost/arena
  permission_check.sh - enforce least privilege (21 tests)
  skill_registry.sh - discover, inspect, validate, load, disable
  cost_telemetry.sh - NEW v1.1: record/show metrics
  knowledge.sh - NEW v1.1: add/validate/promote-check/list
  lib_run.sh - run_step with EXIT_CODE, prefers project.yaml commands (v1.2)
  detect_env.sh, baseline.sh, gate_check.sh (no state.json trust), secret_scan.sh (allow list v1.2), dep_audit.sh (PHP + nested v1.2), report_lint.sh

docs/
  arena/overview.md - NEW v2.0: full arena integration
  architecture/project-profile.md - NEW v1.2: project profile format
  architecture/ - overview, control-plane, knowledge, model-routing, skill-registry
  audit/ - v1.1-baseline.md, v1.1-implementation-audit.md, v1.1-gap-audit.md, v1.1-final-report.md
  state-machine/ - states, transitions, implementation
  agents/ - contracts
  workflows/ - types
  security/ - permissions, skill-security
  recovery/ - recovery
  adapters/ - overview
  evaluation/ - scenarios

references/ (backward compat)
  tiers.md, state-format.md, evidence-rules.md, failure-modes.md, interaction-protocol.md, report-template.md
  lenses/ (7), playbooks/ (6)

evals/
  scenarios.md (15) + scenarios_v1_1.md (35) = 50 + arena 9 = 59 total
  results/ - v2.0-evaluation-report.md (151 PASS), v1.1-evaluation-report.md

tests/
  gates.test.sh (15), state_machine.test.sh (37), permissions.test.sh (21), recovery.test.sh (8), playbook.test.sh (7), arena.test.sh (20 NEW v2.0), project_profile.test.sh (9 NEW v1.2), dep_audit.test.sh = 117+ total v1.2 + 20 arena = 137+
.github/workflows/test.yml - CI full suite v2.1 (gates, state_machine, permissions, recovery, playbook, arena, project_profile, dep_audit, eval, secret_scan, etc.)
```

## 🔒 Hard Rules Enforced

| Rule | Enforcement |
|------|-------------|
| Evidence over claims | `report_lint.sh` + gate_check requires log with EXIT_CODE |
| No state.json trust | G0/G1 re-execute build/test, ignore state.json PASS |
| Independent verification | Verifier fresh context, only spec+diff+logs |
| Arena orchestrator never competes | bracket.py + arena.sh + event log |
| Arena sandboxed | competitors only write inside arena_dir |
| Project profile declares commands | `.eng/project.yaml` + `project_profile.sh --check` |
| Secret allow list with reasons | `.eng/secret_scan.allow` + secret_scan.sh reproduces allow file in log |
| Anti-sycophancy | Must list concrete files checked or explicit clean |
| Loop caps | 2 per gate then escalate to user |
| Token budgets | T0 20k, T1 60k, T2 150k, T3 350k, arena T2 300k, T3 600k |
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
- **Tier 2**: structured 200-1000 LOC, 2-3 lenses, max 3 subagents, ~150k, arena quick 16 agents ~300k
- **Tier 3**: large/prod/legacy >1000 LOC, full audit (security, perf, arch, release), max 6 subagents, ~350k, arena full 100 agents ~600k

## 🧪 Scripts & Exit Codes

| Script | Exit 0 | Exit 1 | Exit 2 | Exit 3 |
|--------|--------|--------|--------|--------|
| `detect_env.sh` | success | error | - | - |
| `baseline.sh` | logs captured (even if tests fail) | script error | - | - |
| `secret_scan.sh` | clean | secrets found | error | - |
| `dep_audit.sh` | no HIGH | HIGH vuln | NOT TESTED (no lockfile/tool error) | NOT APPLICABLE (no deps) |
| `gate_check.sh` | PASS | FAIL | NOT TESTED | NOT APPLICABLE |
| `project_profile.sh` | valid | invalid | - | - |
| `report_lint.sh` | clean | claim without evidence | evidence missing | - |
| `arena.sh` | success | error | - | - |

## 🏟️ Arena Quick Reference (NEW v2.0)

From https://github.com/Jakeschincariol/arena-skill - when Claude keeps giving bad answers, make 100 versions fight to the death.

```bash
# Size it
./scripts/eng.sh arena plan --quick          # 16 agents, 4 rounds, 91 calls
./scripts/eng.sh arena plan --agents 100     # 100 agents, 7 rounds, 595 calls

# Full tournament
./scripts/eng.sh arena run --task "Design auth system" --quick

# Manual flow
./scripts/eng.sh arena init --run RUN-2026-000001 --task "Fix bug" --agents 16 --seed 7
./scripts/eng.sh arena next --run RUN-2026-000001
./scripts/eng.sh arena prompts spawn --run RUN-2026-000001
# Launch waves of 10 Agent tool calls per prompts output, then next, loop
./scripts/eng.sh arena winner --run RUN-2026-000001

# Rubric: correctness 30, completeness 25, specificity 15, robustness 20, clarity 10
# Fatal rule: fatal cannot beat non-fatal
# Strategy cards: 15 reasoning x 12 workflows x 12 strategies = 2160 combos
```

## ✅ Regression Tests

```bash
./tests/gates.test.sh          # 15
./tests/state_machine.test.sh  # 37
./tests/permissions.test.sh    # 21
./tests/recovery.test.sh       # 8
./tests/playbook.test.sh       # 7
./tests/arena.test.sh          # 20 NEW v2.0
./tests/project_profile.test.sh # 9 NEW v1.2
./evals/run_all.sh             # 151 total v2.1 (108 unit + 43 simulated)
```

## 📝 License

MIT - See LICENSE

## 🔖 Version

**2.1.0** - Merged v1.2.1 + v2.0.0. See CHANGELOG.md.

- 151 eval PASS (108 unit: 15 gates + 37 state machine + 21 permissions + 8 recovery + 7 playbook + 20 arena + 9 project_profile + dep_audit, plus 43 simulated)
- 117+ tests v1.2 preserved + 20 arena = 137+
- Project profiles, PHP detection, G5_Project, secret allow list, dep audit PHP/nested
- Arena tournament 100 agents, 2160 cards, attack/defend/judge bracket
- No secrets, no destructive behavior, backward compatible

---

**Built for:** Reliable, inspectable, recoverable, provider-independent engineering orchestration. Evidence > Claims, Tournament > Single-Shot when uncertain, State > Conversation, Contracts > Personas.
