---
name: eng-orchestrator
description: >
  Master engineering orchestration control plane v2.1 with state machine (17 states),
  run manager, event log, 6 agent contracts, permissions, model routing, playbook engine
  (12 workflows inc arena + 15 domains), project profiles (.eng/project.yaml), G5_Project
  gate, secret allow list, PHP detection, preview, recovery, receipt + Arena tournament:
  100 sub-agents compete with distinct strategy cards (15x12x12=2160 combos), attack/defend/judge
  bracket until one survives. WHEN TO USE: any code task beyond Q&A, feature, bugfix, refactor,
  prod work, multi-file, OR when user says bad answer/try again/do better OR explicitly /arena.
  WHEN NOT TO USE: one-line typo, pure Q&A. Persian: "اینو بیلد کن"، "مهندسی حرفه‌ای"،
  "ارکستراسیون کن"، "از صفر بساز"، "مسابقه بده"، "رقابت"، "arena".
version: 2.1.0
---

# eng-orchestrator v2.1 - Control Plane + Project Profiles + Arena

> Evidence > Claims, Tournament > Single-Shot when uncertain, State > Conversation, Contracts > Personas, Least Privilege > Unlimited, Deterministic Gates > Subjective.

## Core Principle
Smallest effective team, but when answer quality uncertain: tournament. Roles are lenses/checklists, not personas. Agents are contracts (inputs/outputs/permissions/tools/model). Subagents for verification and file-disjoint parallel. Arena competitors are ephemeral agents with strategy cards. Project profile declares build/test/lint. See `docs/architecture/overview.md`.

## 0. Run Manager & State Machine + Arena Extension
- Create RUN: `./scripts/run_manager.sh create --type feature --domain web --tier T2 --task "desc"` -> `RUN-2026-000001` with manifest, state, events, artifacts, checkpoints, receipt. Config `config/state_machine.yaml`.
- States: INTAKE, BASELINE, CLASSIFICATION, PLANNING, EXECUTION, VALIDATION, REVIEW, REWORK, VERIFICATION, RELEASE_REVIEW, HUMAN_APPROVAL, COMPLETED, BLOCKED, FAILED, CANCELLED, ESCALATED, RECOVERY (17). See `docs/state-machine/states.md`.
- Arena extension: `config/arena.yaml` - tournament runs inside EXECUTION/VERIFICATION, events ARENA_CREATED, SPAWN_STARTED, ROUND_STARTED, CHAMPION_SELECTED. Arena dir `.eng/runs/RUN/arena/`, state `arena.json` via `skills/arena/bracket.py`.
- Validate: `./scripts/state_machine.sh validate --from EXECUTION --to COMPLETED` must reject. Transition via `transition --run RUN --from X --to Y --actor NAME`.
- Event log: `./scripts/event_log.sh append --run RUN --type GATE_PASSED --actor worker`. Append-only, no secrets.

## 1. Intake & Triage + Arena Trigger Detection + Project Profile
1. `scripts/detect_env.sh --json` -> capabilities, degrade gracefully, mark NOT TESTED.
2. Project profile: `.eng/project.yaml` declares build/test/lint + gate extras + secret allow. `scripts/project_profile.sh --check` validates. `detect_cmds` prefers it over heuristics (PHP before pytest). See `docs/architecture/project-profile.md`. Without profile, v1.1 detection unchanged.
3. Create `.eng/` from templates, fill `brief.md`.
4. Classify: PROJECT TYPE, DOMAINS (15), RISK, COMPLEXITY, WORKFLOW TYPE (feature, bug-fix, refactor, migration, performance, security, investigation, testing, release, documentation, incident, arena). See `workflows/`.
5. Choose Tier 0-3 per `references/tiers.md`. Tier != Model.
6. Arena trigger: explicit `/arena`, "arena", "make them compete", "مسابقه بده", "رقابت" -> always run. Implicit "that's wrong", "bad answer", "try again", "do better", "اشتباهه", "دوباره" -> ask first: full (100, 595 calls, 7 rounds) vs quick (16, 91 calls, 4 rounds) vs retry. See `config/arena.yaml`.
7. Max 3 batched questions upfront per `references/interaction-protocol.md`, else ASSUMED.

## 2. Playbook Engine + Strategy Cards (2160 combos) + Project Gates
- Compose: base workflow + domain overlay + risk overlay + tier + constraints.
- `scripts/playbook_engine.sh compose --type feature --domain wordpress --risk security:high --tier T3 --out .eng/plan.md`
- Workflows 12 in `workflows/*.yaml` (11 + arena), domains 15 in `domains/*.yaml`. See `docs/workflows/types.md`.
- Arena cards: `skills/arena/strategies.json` - 15 reasoning x 12 workflows x 12 strategies = 2160 distinct. Dealer ensures no repeats, balanced even spread.
- Project profile extras: `G5_Project` gate runs `gates.extras` from `.eng/project.yaml` via `run_step`, logs `.eng/artifacts/profile_<name>.log` with EXIT_CODE. Part of `gate all`. See `docs/architecture/project-profile.md`.
- Preview no mutation: `./scripts/preview.sh --type feature --task "desc"` or `./scripts/eng.sh preview` or `./scripts/eng.sh arena plan --quick`. Must NOT mutate repo.

## 3. Baseline First
Run `scripts/baseline.sh` BEFORE change. Produces `baseline_build.log` and `baseline_test.log` with `EXIT_CODE`. Save to `evidence.md`. For arena, baseline is previous rejected answer -> `.eng/runs/RUN/arena/baseline.md` for final blind check. See `references/evidence-rules.md`.

## 4. Branch / Checkpoint / Worktree
- Branch: `git checkout -b eng/<task>-<date>` or worktree isolation: `./scripts/worktree.sh create --run RUN --branch run/RUN`.
- Checkpoint: copy to `.eng/runs/RUN/checkpoints/` and emit `CHECKPOINT_CREATED`.
- Worktree detects uncommitted user changes, never destroys automatically. Cleanup: `worktree.sh cleanup --older-than 7d --dry-run`. See `docs/recovery/recovery.md`.

## 5. Agent Contracts & Permissions + Arena Competitors
- Contracts in `agents/*.yaml`: name, role, purpose, inputs, outputs, capabilities, permissions, tools, model_policy, delegation, termination, failure_policy, evidence_required. See `docs/agents/contracts.md`.
- Permissions in `config/permissions.yaml`: filesystem.read/write, shell restricted/execute, network deny/limited, git read/write, dependency limited, secret.read deny (only human). Enforce via `scripts/permission_check.sh check --agent NAME --tool TOOL`. See `docs/security/permissions.md`.
- Arena competitors: ephemeral agents extending worker/reviewer/verifier but sandboxed to `.eng/runs/RUN/arena/` only. Orchestrator never competes/judges. See `config/arena.yaml`.
- Model routing in `config/model_policy.yaml`: Tier != Model, low/medium/high reasoning, adapters in `adapters/` (claude, codex, copilot, generic) with real `adapter.py`. See `docs/architecture/model-routing.md`.

## 6. Build & Hard Gates (Executable Only)
- Use `scripts/lib_run.sh`: `run_step current build <cmd>` -> log with `EXIT_CODE`. Resolution order: `.eng/project.yaml` commands -> package.json -> composer.json -> tests/run.php -> go.mod/pytest/Makefile/gradlew -> phpunit.xml. PHP checked before pytest (fixes WordPress).
- Gates: G0 Build `build exit 0`, G1 Tests `tests >= baseline AND no new failures`, G2 Lens `no open HIGH+`, G3 Security `secret_scan exit 0 AND no HIGH vuln` (allow list `.eng/secret_scan.allow` with reasons), G4 Release `artifact hash verified`, G5_Project `project extras PASS`.
- Check: `./scripts/gate_check.sh <gate> [--no-run]`. Arena: rubric scoring replaces lens review, champion must pass secret_scan. See `references/tiers.md`.

## 7. Review / Rework Bounded Loop + Arena Attack/Defend/Judge
- Normal: IMPLEMENT -> VALIDATION -> REVIEW -> PASS -> VERIFY / FAIL -> REWORK -> VALIDATION -> REVIEW. Max cycles 2 per gate, then ESCALATED. No infinite loop. See `docs/state-machine/transitions.md`.
- Arena extended verification: per match Attack (2) -> Defend (2) -> Judge (1) -> collect -> advance. Attack format: `ATTACK N [FATAL|MAJOR|MINOR] title / Where / Problem` with WRONG/MISSING/BREAKS/VAGUE. Defend: `ATTACK N: CONCEDE|REBUT`. Judge: JSON with scores correctness 30, completeness 25, specificity 15, robustness 20, clarity 10, fatal rule, tie breakers. See `skills/arena/rubric.md`.

## 8. Independent Verification + Arena as Escalation
- Tier 1+: verifier fresh context only spec+diff+logs. Runs `gate_check.sh --no-run`. Mark NOT TESTED if cannot run. See `references/evidence-rules.md`.
- When verification fails or user dissatisfied: escalate to arena. Arena is alternative verification with 16-100 perspectives. Final check: blind comparison champion vs rejected answer if baseline exists.

## 9. Arena Tournament Mode (v2.0)
- Tool: `skills/arena/bracket.py` wrapped by `scripts/arena.sh` for control plane integration. State in `.eng/runs/RUN/arena/arena.json`, LATEST symlink, one JSON holds whole tournament, survives compaction, resume via `next`.
- Size it: `arena.sh plan --agents N` or `--quick` (16). Prints rounds, calls, waves. 100 agents = 7 rounds, 595 calls; 16 = 4 rounds, 91 calls. Default wave 10 matches Claude Code concurrency.
- Task file: write `.eng/runs/RUN/arena/task.md` standalone - request in user's words, every requirement/constraint, context paths/data, what done looks like, what user disliked. Sub-agents cannot see conversation, only task file. Never add requirements, never write your view.
- Init: `arena.sh init --run RUN --task "desc" --agents N --seed S --baseline-file old.md` -> deals cards no repeats, pairs round1, writes arena.json. Also `eng.sh arena init`.
- Loop: always `arena.sh next --run RUN` tells next step and exact command. Then `arena.sh prompts <phase> --run RUN` writes briefs, list jobs in waves. Launch one wave at a time: one Agent tool call per job, subagent_type general-purpose, description `arena <job id>`, prompt `Read <path> and follow exactly`, run_in_background false, wait wave complete. After last wave `next`. If output missing, prompts lists only missing, re-run once, if fails twice write `NO OUTPUT` (missing attack = no attacks, missing solution loses, judge fails twice -> third fresh run, never decide yourself). Order: spawn once, then per round attack->defend->judge->collect->advance, final once if baseline, DONE.
- Result: `arena.sh winner --run RUN` prints champion path, read only that file. Present: winning solution full, why it won (attacks survived, short list), card one line (reasoning+workflow+strategy), rounds "7 rounds, 100 in, 1 left", baseline comparison scores honestly if old higher say so, where full record lives. If solution changes project files, ask apply or change, don't apply automatically.
- Rules: orchestrator never competes/attacks/judges, never picks winner, collect records judges, record only for bookkeeping fix when user asks. Every sub-agent gets identical task byte-for-byte via brief, never paraphrase or add hint. Never read solutions/attacks/verdicts during run, only via status/pairings/next. Run from dir where init ran (.arena/LATEST). Sub-agents only write inside arena_dir, tell user if outside. If user says stop, stop, status shows where, next resumes.
- Full command: `eng.sh arena run --task "desc" --quick` -> creates run, init, guidance. See `workflows/arena.yaml`, `config/arena.yaml`.

## 10. Recovery
- Detect stale: `scripts/recovery.sh detect`
- Inspect: `recovery.sh inspect --run RUN` shows last valid state/event/artifact/checkpoint/git/fs/worktree/unfinished
- Reconcile: checks uncommitted, divergence, checkpoint age, never blindly resume unsafe
- Recover: `recovery.sh recover --run RUN` -> restore checkpoint -> resume EXECUTION or escalate. Arena: state on disk, `arena.sh next` resumes after compaction. See `docs/recovery/recovery.md`.

## 11. Receipt & Audit + Arena + Project Profile
- Generate: `scripts/receipt.sh generate --run RUN` -> receipt.json answering why tier/agents/gates selected, why workflow/domain/risk selected, tools used, permissions, evidence, rework cycles, human approval, cost breakdown, project profile used. Arena adds rounds, agents, champion card, attacks survived, baseline comparison. See spec section 18.
- Event log append-only, no secrets, arena events logged too.

## 12. Skill Registry & Security + Cost & Knowledge + Secret Allow
- Registry: `scripts/skill_registry.sh {discover|inspect|validate|load|disable}`. Validates manifest, permissions, integrity, suspicious patterns. No auto remote exec. Arena skill registered as `skills/arena/` with bracket.py, strategies.json, rubric.md. See `docs/architecture/skill-registry.md`.
- Secret scan: `scripts/secret_scan.sh` checks for secrets, allow list `.eng/secret_scan.allow` with mandatory reasons per entry, logs full allow file in report (v1.2.1). See `docs/security/permissions.md`.
- Cost: `scripts/cost_telemetry.sh record --run RUN --metric NAME --value VAL` optional via ENG_TELEMETRY=1, updates state.json budget, arena tracks per agent.
- Knowledge: `.eng/knowledge/` lessons/failures/decisions/patterns/regressions, promotion freq>=3 or 1 CRITICAL, check modification allowed only human/architect. Arena champion card+why -> lesson if applicable.
- Anti-sycophancy: No PASS without artifact. Statuses SOLVED, UNSOLVED, BLOCKED, NOT TESTED, NOT APPLICABLE, ASSUMED. Run `report_lint.sh` before final.

## 13. Stopping Rules (Measurable)
Stop when: requirements met + acceptance + required gates PASS/NA + no BLOCKED HIGH + report_lint PASS. Arena stop when champion selected and winner presented. Stop on token budget (T0 20k, T1 60k, T2 150k, T3 350k, arena T2 300k, T3 600k due to N agents) or loop cap.

## 14. Final Delivery
Report from `references/report-template.md` + `receipt.json`. User language = user's language. For arena, include winning solution full + why won + card + rounds + baseline comparison. Record lessons in structured knowledge per promotion rule.

## File Map v2.1
- `config/state_machine.yaml`, `permissions.yaml`, `model_policy.yaml`, `arena.yaml` (v2.0)
- `agents/*.yaml` - 6 contracts
- `workflows/*.yaml` (12 incl arena) - work types, `domains/*.yaml` (15) - overlays
- `skills/arena/` - arena subskill: bracket.py (1235 lines), strategies.json (2160 cards), rubric.md, SKILL.md
- `.eng/project.yaml` template, `.eng/templates/project.yaml`, `.eng/secret_scan.allow` (v1.2)
- `adapters/*/` - provider abstraction with adapter.py + yaml
- `scripts/` control plane: state_machine.sh, event_log.sh, run_manager.sh, playbook_engine.sh, preview.sh, recovery.sh, worktree.sh, receipt.sh, permission_check.sh, skill_registry.sh, eng.sh, arena.sh (v2.0), project_profile.py/.sh (v1.2), cost_telemetry.sh, knowledge.sh, lib_run.sh, detect_env.sh, baseline.sh, gate_check.sh, secret_scan.sh, dep_audit.sh, report_lint.sh
- `docs/` - architecture (incl project-profile.md, arena/overview.md), state-machine, agents, workflows, security, recovery, evaluation, adapters, audit
- `references/` - tiers, lenses, playbooks (backward compat)
- `.eng/knowledge/` - structured knowledge, `evals/` - 151 scenarios (108 unit + 43 simulated) v2.0, 117 v1.2
