# 🛡️ eng-orchestrator - Control Plane v1.2.0

[![Tests](https://github.com/obsifox/eng-orchestrator/actions/workflows/test.yml/badge.svg)](https://github.com/obsifox/eng-orchestrator/actions/workflows/test.yml)
[![Version](https://img.shields.io/badge/version-1.2.0-blue.svg)](CHANGELOG.md)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Skill](https://img.shields.io/badge/skill-control%20plane-orange.svg)](SKILL.md)

> **Engineering Orchestration Control Plane** — Turns AI agent into adaptive org with state machine, run manager, event log, agent contracts, permissions, model routing, playbook engine, preview, recovery, receipt.

**v1.2.0 (current):** Project profiles (`.eng/project.yaml`) + PHP/Composer detection, `G5_Project` gate for project-defined extras, secret-scan allow list with mandatory reasons (17 new asserts, 105 total).

**v1.1.0:** State machine (17 states, 37 tests), Run Manager (RUN-xxx isolation), Event Log (23 types), Agent Contracts (6), Permission Matrix (21 tests, least privilege), Model Routing (Tier != Model), Playbook Engine (11 workflows + 4 domains), Preview (no mutation), Recovery (8 tests), Worktree Isolation, Receipt, Skill Registry, Adapters, 50 eval scenarios.

**v1.0.1 Fix:** No gate trusts `state.json` for PASS. Only real command outputs with `EXIT_CODE`.

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
# 0. Declare how THIS project builds, tests and lints (v1.2)
cat .eng/project.yaml            # commands + gate extras + secret allow file
./scripts/project_profile.sh --check

# 1. Agent reads SKILL.md (94 lines, <150)
cat SKILL.md

# 2. Preview without mutation (v1.1)
./scripts/eng.sh preview --type feature --task "Add auth"
# or ./scripts/preview.sh --type feature --task "Add auth"

# 3. Create isolated run
./scripts/eng.sh run create --type feature --domain web --tier T2 --task "Add API"
# -> RUN-2026-000001 with manifest.json, state.json, events.jsonl

# 4. State machine validation (deterministic)
./scripts/eng.sh state validate --from EXECUTION --to COMPLETED
# -> INVALID: Must go through VALIDATION, REVIEW, VERIFICATION

# 5. Baseline BEFORE any change
./scripts/baseline.sh
# -> .eng/artifacts/baseline_build.log (EXIT_CODE)
# -> .eng/artifacts/baseline_test.log

# 6. Build & check gates (real execution, no state.json trust)
./scripts/eng.sh gate G0_Build
./scripts/eng.sh gate G1_Tests
./scripts/eng.sh gate G2_Lens --no-run
./scripts/eng.sh gate all

# 7. Run all tests (105 PASS)
./tests/gates.test.sh          # 15
./tests/state_machine.test.sh  # 37
./tests/permissions.test.sh    # 21
./tests/recovery.test.sh       # 8
./tests/playbook.test.sh       # 7

# 8. Generate receipt
./scripts/eng.sh receipt generate --run RUN-2026-000001
# -> .eng/runs/RUN-xxx/receipt.json answering why tier/agents/gates
```

## 📁 File Tree v1.1

```
SKILL.md (94 lines) - control plane, triggers: "build this", "اینو بیلد کن"
CHANGELOG.md - v1.0.0 -> v1.0.1 -> v1.2.0
LICENSE (MIT)

config/
  state_machine.yaml - 17 states, transitions
  permissions.yaml - least privilege matrix
  model_policy.yaml - Tier != Model, adapters

agents/ (6 contracts)
  architect.yaml, worker.yaml, reviewer.yaml, security-reviewer.yaml, verifier.yaml, release-manager.yaml

workflows/ (11 types)
  feature, bug-fix, refactor, migration, performance, security, investigation, testing, release, documentation, incident

domains/ (4 overlays, extensible)
  wordpress, android, web, backend + legacy playbooks in references/playbooks/ (6)

adapters/
  generic (always), claude, codex, copilot (placeholder) - provider-independent

scripts/ (control plane + gates)
  eng.sh - main CLI: preview, run, list, show, state, event, recover, worktree, receipt, registry, playbook, gate
  state_machine.sh - list-states, validate, transition, current, history (37 tests)
  event_log.sh - append-only events.jsonl, 23 types
  run_manager.sh - create RUN-YYYY-XXXXXX with manifest, state, events, artifacts, checkpoints, receipt
  playbook_engine.sh - compose base+domain+risk+tier
  preview.sh - eng preview, no mutation
  recovery.sh - detect, inspect, reconcile, recover, resume (8 tests)
  worktree.sh - isolated worktree per run
  receipt.sh - receipt.json generation
  permission_check.sh - enforce least privilege (21 tests)
  skill_registry.sh - discover, inspect, validate, load, disable
  lib_run.sh - run_step with EXIT_CODE; detect_cmds (profile -> manifests -> heuristics)
  project_profile.sh / project_profile.py - read .eng/project.yaml (v1.2)
  detect_env.sh, baseline.sh, gate_check.sh (no state.json trust), secret_scan.sh, dep_audit.sh, report_lint.sh

docs/
  audit/ - v1.1-baseline.md, v1.1-implementation-audit.md
  architecture/ - overview, control-plane, knowledge, model-routing, skill-registry
  state-machine/ - states, transitions, implementation
  agents/ - contracts
  workflows/ - types
  security/ - permissions, skill-security
  recovery/ - recovery
  adapters/ - overview
  evaluation/ - scenarios
  architecture/project-profile.md - .eng/project.yaml contract (v1.2)

references/ (backward compat)
  tiers.md, state-format.md, evidence-rules.md, failure-modes.md, interaction-protocol.md, report-template.md
  lenses/ (7), playbooks/ (6)

evals/
  scenarios.md (15) + scenarios_v1_1.md (35) = 50 total
  results/ - real executed with/without

examples/ - good vs bad plan/verify/review (structured findings)
.eng/templates/ - brief, plan, decisions, evidence, state.json, project.yaml (v1.2)
.eng/knowledge/ - lessons/, failures/, decisions/, patterns/, regressions/
tests/
  gates.test.sh (15 asserts), state_machine.test.sh (37), permissions.test.sh (21),
  recovery.test.sh (8), playbook.test.sh (7), project_profile.test.sh (17) = 105 total
.github/workflows/test.yml - CI
```

## 🔒 Hard Rules Enforced

| Rule | Enforcement |
|------|-------------|
| Evidence over claims | `report_lint.sh` + gate_check requires log with EXIT_CODE |
| No state.json trust | G0/G1 re-execute build/test, ignore state.json PASS |
| Independent verification | Verifier fresh context, only spec+diff+logs |
| Anti-sycophancy | Must list concrete files checked or explicit clean |
| Allow list discipline | A secret-scan allowance needs pattern + path + reason; a silent ignore is impossible |
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

## 🧭 Project profile (v1.2)

`lib_run.sh detect_cmds` used to guess from file names — and guessed wrong for PHP (a
`tests/` directory looked like pytest). A repository now states its commands once:

```yaml
# .eng/project.yaml
name: DashWoo
commands:
  build: php bin/build.php --out=/home/user/releases
  test: php tests/run.php
  lint: php bin/lint.php
gates:
  extras:
    - name: docs_in_sync
      command: python3 tools/docs/generate.py --check
      required: true
    - name: upload_verify
      command: python3 tools/verify-upload.py 1.6.0
      required: false
secret_scan:
  allow: .eng/secret_scan.allow
```

| Piece | Behaviour |
| --- | --- |
| detection order | profile -> `package.json` -> `composer.json` / `tests/run.php` -> go/pytest/Makefile/gradle -> `phpunit.xml` |
| `G5_Project` | runs `gates.extras`; required failure = FAIL, optional failure = warning, no profile = NOT APPLICABLE |
| allow list | `.eng/secret_scan.allow`, entries `pattern \| path \| reason`; no path or no reason means the entry does not apply |
| validation | `python3 scripts/project_profile.py --check` (0 ok, 3 none, 4 empty, 5 malformed) |

Full details: `docs/architecture/project-profile.md`. Tests: `tests/project_profile.test.sh` (17).

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

**1.2.0** - Control Plane release. See CHANGELOG.md and `docs/audit/v1.1-implementation-audit.md` for full audit.

- 88 tests PASS (15 gates + 37 state machine + 21 permissions + 8 recovery + 7 playbook)
- 50 eval scenarios (15 existing + 35 new)
- No secrets, no destructive behavior, backward compatible

---

**Built for:** Reliable, inspectable, recoverable, provider-independent engineering orchestration. Evidence > Claims, State > Conversation, Contracts > Personas.
