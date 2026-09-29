---
name: eng-orchestrator
description: >
  Master engineering orchestration skill that turns a single AI agent into an
  adaptive engineering org (Tier 0-3). WHEN TO USE: any code task beyond Q&A,
  feature implementation, bugfix in codebase, architecture, refactor, production
  work, multi-file projects. WHEN NOT TO USE: one-line typo explanation,
  pure Q&A / research without code change, chatting, simple text rewrite.
  Persian triggers: "اینو بیلد کن"، "پروژه رو مهندسی کن"، "از صفر بساز"،
  "مهندسی حرفه‌ای"، "تیم مهندسی بساز"، "ارکستراسیون کن".
version: 1.0.1
---

# eng-orchestrator - Mother Skill

> v1.0.1 - Gate hardening: no gate trusts state.json, only real command logs with EXIT_CODE. See CHANGELOG.



## Core Principle
Smallest effective team for this specific project. Roles are lenses (checklists), not personas. Subagents only for independent verification and file-disjoint parallel work.

## 0. Detect Environment
Run `scripts/detect_env.sh`. Record capabilities in `.eng/state.json`. If git/test runner/subagent unavailable, degrade gracefully and mark affected gates NOT TESTED. See `references/state-format.md`.

## 1. Intake & Triage (MANDATORY FIRST)
1. Create `.eng/` from `.eng/templates/`. Fill `brief.md`.
2. Classify: PROJECT TYPE, DOMAINS, RISK, COMPLEXITY. See `references/tiers.md`.
3. Choose Tier 0-3 with explicit entry criteria. Log in `decisions.md`.
4. Max 3 batched clarifying questions upfront (see `references/interaction-protocol.md`). Otherwise state ASSUMED assumptions in evidence ledger.
5. Identify minimum lenses needed. Do not load all. See `references/lenses/`.

## 2. Baseline First
Run `scripts/baseline.sh` BEFORE any change. Save output to `.eng/evidence.md`. Detect regressions later. Status rules in `references/evidence-rules.md`.

## 3. Branch / Checkpoint
If git exists: `git checkout -b eng/<task>-<date>` or stash. If no git: copy files to `.eng/checkpoint/`.

## 4. Plan (Tier 1+ requires plan.md)
Load `references/playbooks/<domain>.md` if applicable (on-demand).
Write `.eng/plan.md` with Task Graph, Dependencies, Acceptance Criteria. Keep proportional to Tier.

## 5. Build
Implement per plan. Respect existing conventions. No destructive actions without user approval (delete files, DB schema, add deps, arch change).

## 6. Hard Gates - Executable Only
Each gate must have checkable condition. Use `scripts/gate_check.sh <gate>`.
Gates:
- G0 Build: `build exit 0`
- G1 Tests: `tests >= baseline AND no new failures`
- G2 Lens Reviews: `no open HIGH+ finding` (see lenses)
- G3 Security: `secret_scan exit 0 AND no HIGH vuln`
- G4 Release: `artifact == reviewed source`

Max 2 remediation cycles per gate, then escalate to user. See `references/tiers.md`.

## 7. Independent Verification (MANDATORY for Tier 1+)
Verifier runs in fresh context: sees only spec + diff + command outputs. Not your opinion. If subagents unavailable, do separate pass with isolated prompt. Mark NOT TESTED if cannot run.

## 8. Anti-Sycophancy & Evidence
No PASS without artifact (command output, file, diff). Allowed statuses: SOLVED, UNSOLVED, BLOCKED, NOT TESTED, NOT APPLICABLE, ASSUMED. Run `scripts/report_lint.sh` before final report. See `references/evidence-rules.md`.

## 9. Failure Modes
Check `references/failure-modes.md` for detection/mitigation of: False Completion, Hallucinated Validation, Over/Under-Delegation, Context Drift, Architecture Drift, Infinite Review Loop, Over/Under-Engineering, Scope Explosion, Role Explosion, Persona Theater, Stale Context, Parallel File Conflicts.

## 10. Stopping Rules (measurable)
Stop when: requirements met + acceptance criteria met + required gates PASS/NOT APPLICABLE + no BLOCKED HIGH + report_lint PASS. Stop on token budget (Tier0:20k, T1:60k, T2:150k, T3:350k est) or loop cap hit.

## 11. Final Delivery
Produce report from `references/report-template.md`. User-facing language = user's language (Persian if user writes Persian). Technical terms stay English. Record lessons in `lessons.md` per promotion rule.

## File Map
- `references/tiers.md` - tier definitions
- `references/state-format.md` - .eng schema
- `references/evidence-rules.md` - evidence ledger
- `references/failure-modes.md`
- `references/interaction-protocol.md`
- `references/report-template.md`
- `references/lenses/*.md` - load on demand
- `references/playbooks/*.md` - domain checklists
- `scripts/*` - executable checks
