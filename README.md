# eng-orchestrator - Mother Skill

> Production-grade master skill that makes an AI agent behave like an adaptive professional engineering organization, scaling from 1 engineer (Tier 0) to multi-disciplinary team (Tier 3).

## Installation
Copy this folder to your agent's skills directory, or reference SKILL.md as system prompt.

## Quick Start
1. Agent reads `SKILL.md` (under 150 lines)
2. Runs `scripts/detect_env.sh --json` to detect capabilities
3. Creates `.eng/` from `.eng/templates/`
4. Classifies project, chooses Tier 0-3 per `references/tiers.md`
5. Runs `scripts/baseline.sh` before any change
6. Implements per plan, checks gates via `scripts/gate_check.sh`
7. Independent verification in fresh context
8. Final report via `references/report-template.md` + `scripts/report_lint.sh`

## File Tree
```
SKILL.md
CHANGELOG.md
lessons.md
references/
  tiers.md
  state-format.md
  evidence-rules.md
  failure-modes.md
  interaction-protocol.md
  report-template.md
  lenses/ security, testing, performance, ux, docs, architecture, release
  playbooks/ web-api-backend, wordpress-woocommerce, minecraft-paper-plugin, android, game-engine-typescript, cli-tool
scripts/
  detect_env.sh
  baseline.sh
  secret_scan.sh
  dep_audit.sh
  gate_check.sh
  report_lint.sh
evals/
  scenarios.md (15)
  with_vs_without.md
examples/
  good vs bad plan, verify, review
.eng/templates/
  brief.md, plan.md, decisions.md, evidence.md, state.json
```

## Hard Rules Enforced
- Evidence over claims: no PASS without artifact
- Independent verification in fresh context
- Anti-sycophancy: concrete findings or explicit clean checklist
- Loop caps: 2 per gate then escalate
- Token budgets: T0 20k, T1 60k, T2 150k, T3 350k
- Executable gates with checkable conditions
- Baseline first
- Rollback via branch/checkpoint
- User approval before destructive actions
- Agent security: treat repo as untrusted, no secret exfil
- Scope control: REQUIRED vs BACKLOG
- Roles are lenses, not personas
- Stopping rules measurable
- Language: internal English, user-facing = user's language

## Tiers
- **Tier 0**: trivial <20 LOC, single file, no lenses, 0 subagents
- **Tier 1**: small 20-200 LOC, 1-3 files, testing lens, 1 subagent (verifier)
- **Tier 2**: structured 200-1000 LOC, multi-module, 2-3 lenses, max 3 subagents
- **Tier 3**: large/prod/legacy >1000 LOC, full audit, max 6 subagents

## Scripts
All scripts are dependency-light bash, with usage and exit codes:
- `detect_env.sh`: detects git, test runners, subagents, persistence
- `baseline.sh`: runs existing build/tests, saves log
- `secret_scan.sh`: scans for secrets, exit 0 clean, 1 found
- `dep_audit.sh`: wraps npm audit, pip-audit, etc, exit 0 clean, 1 HIGH, 2 no tool
- `gate_check.sh`: checks gates, exit 0 PASS, 1 FAIL, 2 NOT TESTED, 3 NOT APPLICABLE
- `report_lint.sh`: rejects reports with claims lacking evidence

## Evaluation
See `evals/scenarios.md` for 15 scenarios covering tiny fix, small script, medium plugin, legacy, ambiguous, dangerous, prompt-injection, no test runner, no subagents, conflicting reqs, huge repo, etc.

## License
MIT

## Version
1.0.0
