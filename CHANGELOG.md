# Changelog

All notable changes to eng-orchestrator skill.

## 2.1.0 - 2026-09-29
### Added - Merged v1.2.1 + v2.0.0 -> v2.1.0 (Major)
- **Merge:** v1.2.0 (project profiles, PHP detection, G5_Project, secret allow list) + v1.2.1 (dep audit PHP/nested, timezone-aware, secret allow full log) + v2.0.0 (arena tournament) = v2.1.0. Resolves rebase conflict, preserves all features.
- **Project Profiles (v1.2):** `.eng/project.yaml` declares build/test/lint + gate extras + secret allow file, `scripts/project_profile.py` (8.5K) + `scripts/project_profile.sh` (505B), template `.eng/templates/project.yaml`, example `examples/project.yaml`, doc `docs/architecture/project-profile.md`. `detect_cmds` prefers profile over heuristics, PHP checked before pytest (fixes WordPress tests/ dir mis-detection), composer.json, phpunit.xml support.
- **G5_Project Gate:** Runs extras from `.eng/project.yaml` via `run_step`, logs `.eng/artifacts/profile_<name>.log` with EXIT_CODE, part of `gate all`, statuses PASS/FAIL/WARNING/NOT APPLICABLE/NOT TESTED.
- **Secret Allow List (v1.2):** `.eng/secret_scan.allow` with mandatory reasons, `secret_scan.sh` reproduces allow file in full in log, reports hits allowed (v1.2.1).
- **Dep Audit PHP (v1.2.1):** Understands PHP and nested manifests (composer.lock, package-lock.json, etc.), timezone-aware timestamps.
- **Arena (v2.0 preserved):** skills/arena/ (bracket.py 1235 lines, strategies.json 2160 cards, rubric.md, SKILL.md), config/arena.yaml, workflows/arena.yaml, scripts/arena.sh, docs/arena/overview.md, tests/arena.test.sh 20 PASS, 151 eval PASS.
- **File Map v2.1:** Adds .eng/project.yaml, .eng/secret_scan.allow, .eng/templates/project.yaml, docs/architecture/project-profile.md, scripts/project_profile.py/.sh, examples/project.yaml, tests/project_profile.test.sh, tests/dep_audit.test.sh.

### Changed - v2.1 Merge
- **SKILL.md:** v2.0.0 ~180 lines -> v2.1.0 ~200 lines, version 2.1.0, added section 1 project profile (detect_cmds order, .eng/project.yaml), section 2 G5_Project, section 6 secret allow list + PHP detection, section 11 secret allow, file map v2.1 includes project profile + arena. Keeps all v2.0 arena section 9.
- **README.md:** Updated to v2.1.0 with project profiles + arena, badges, quick start includes project_profile.sh --check and arena run, file tree v2.1 with both v1.2 and v2.0 files, hard rules includes arena sandboxed + project profile + secret allow, tiers includes arena token budgets, arena quick reference.
- **eng.sh:** Merged v1.2 (project_profile commands) + v2.0 (arena, knowledge, cost) -> v2.1 with all commands.
- **test.yml:** Merged v1.2 (project_profile tests, dep_audit, secret allow, PHP) + v2.0 (arena tests) -> v2.1 full suite.
- **evals/run_all.sh:** Updated to 151 PASS (108 unit + 43 simulated) v2.1.

### Preserved - All v1.2.1 + v2.0 Features
- v1.2.1: project profiles, PHP detection, G5_Project, secret allow, dep audit PHP/nested, 117 tests
- v2.0: arena tournament 100 agents, 2160 cards, attack/defend/judge, 20 tests PASS, 151 eval PASS
- v1.1: 17-state machine 37 tests, run manager, event log 23 types, 6 agents, permissions 21 tests, model routing 3 adapter.py, playbook 12 workflows (11+arena) + 15 domains, preview, recovery 8 tests, worktree cleanup, receipt enrichment, cost telemetry, knowledge promotion, 88 tests

## 2.0.0 - 2026-09-29
### Added - Arena Tournament Mode (Major Rewrite)
- **Arena Integration:** Installed `skills/arena/` from https://github.com/Jakeschincariol/arena-skill (MIT) - bracket.py 1235 lines, strategies.json 2160 cards, rubric.md, ARENA_SKILL.md original. Integrated as escalation mode when user dissatisfied or explicitly /arena.
- **Strategy Cards:** 15 reasoning modes (first-principles, inversion, analogy, adversarial, constraint-first, worked-example, socratic, contrarian, systems-thinking, decomposition, working-backwards, probabilistic, dialectical, evidence-first, expert-panel) x 12 workflows (draft-critique-rewrite, outline-first, test-first, research-then-synthesise, three-drafts, requirements-checklist, iterative-deepening, build-then-break, smallest-version-first, options-matrix, open-questions-first, write-then-restructure) x 12 strategies (simplest, maximal-rigour, user-empathy, edge-cases-first, speed, defensive, etc.) = 2160 distinct combos. Dealer via proper edge-coloring (Konig + de Werra), no repeats, balanced even spread.
- **Bracket Engine:** `config/arena.yaml` + `workflows/arena.yaml` + `scripts/arena.sh` wrapper around bracket.py. State in `.eng/runs/RUN/arena/arena.json` (not .arena/ root), LATEST symlink, single JSON survives context compaction, resume via next. 100 agents = 7 rounds, 595 calls; 16 agents = 4 rounds, 91 calls; waves of 10 matching Claude Code concurrency.
- **Tournament Phases:** spawn (N competitors write solutions) -> per round attack (2 per match, WRONG/MISSING/BREAKS/VAGUE, max 7, FATAL/MAJOR/MINOR) -> defend (2 per match, CONCEDE/REBUT + revised solution) -> judge (1 per match, rubric scoring) -> collect -> advance -> final blind check vs baseline if exists -> DONE -> winner.
- **Rubric:** correctness 30, completeness 25, specificity 15, robustness 20, clarity 10, weighted total 0-100, fatal rule (fatal cannot beat non-fatal), tie breakers fewer standing attacks -> higher correctness -> judge choice. Mirrors bracket.py WEIGHTS and rubric.md.
- **Control Plane Integration:** Run manager creates arena dir inside run, event log ARENA_CREATED/SPAWN_STARTED/ROUND_STARTED/CHAMPION_SELECTED, permissions competitors sandboxed to arena_dir only (worker/reviewer/verifier base), cost telemetry per agent if ENG_TELEMETRY=1, receipt includes rounds/agents/champion card/attacks survived/baseline comparison, recovery via arena.json on disk.
- **Trigger Detection:** Explicit /arena, arena, make them compete, مسابقه بده, رقابت -> always run. Implicit that's wrong, bad answer, try again, do better, اشتباهه, دوباره, جواب بد -> ask first full vs quick vs retry. Configured in config/arena.yaml.
- **Orchestrator Rules:** Never competes/attacks/judges, never picks winner, every sub-agent gets identical task byte-for-byte via brief, never read solutions during run, only via status/pairings/next, sub-agents only write inside arena_dir, stop on user request, suggest accept-edits mode before spawn.
- **CLI:** `eng.sh arena {plan|run|init|next|prompts|check|pairings|collect|record|advance|status|winner|card}` + `arena.sh` wrapper. `eng.sh arena run --task "desc" --quick` full flow creates run + init + guidance.
- **Docs:** `docs/arena/overview.md` with full integration details, prompt templates, safety.
- **File Map v2.0:** Added skills/arena/ (4 files), config/arena.yaml, workflows/arena.yaml, scripts/arena.sh, docs/arena/overview.md. SKILL.md rewritten 94 -> ~180 lines with arena section 9, file map updated.

### Changed - v2.0 Rewrite
- **SKILL.md:** Complete rewrite v1.1.0 94 lines -> v2.0.0 ~180 lines, version 2.0.0, added arena mode section 9 with full tournament flow, strategy cards, rubric, trigger detection, orchestrator rules, file map v2.0, kept all control plane sections 0-8,10-14. Still evidence > claims, verification > self-assessment.
- **README.md:** Updated to v2.0.0 with arena badges, description control plane + arena, quick start includes arena examples.
- **eng.sh:** Added arena, knowledge, cost commands, updated help to show core + arena sections.
- **.gitignore:** Already ignores .eng/runs/, added .arena/ for arena compatibility (but we use .eng/runs/RUN/arena/).

### Preserved - All v1.1 Control Plane Features
- State machine 17 states, 37 tests PASS
- Run manager RUN-xxx isolation
- Event log 23+ types
- 6 agent contracts
- Permission matrix 21 tests
- Model routing with 3 adapter.py implementations
- Playbook engine now 12 workflows (11 + arena) + 15 domains
- Preview no mutation (including arena plan)
- Recovery 8 tests
- Worktree isolation + cleanup
- Receipt enrichment
- Cost telemetry
- Knowledge promotion
- Skill registry
- 88 tests + 122 eval PASS maintained

## 1.1.0 - 2026-09-29
### Added - Architecture Gap Closure (Control Plane)
- **State Machine:** 17 canonical states (INTAKE, BASELINE, CLASSIFICATION, PLANNING, EXECUTION, VALIDATION, REVIEW, REWORK, VERIFICATION, RELEASE_REVIEW, HUMAN_APPROVAL, COMPLETED, BLOCKED, FAILED, CANCELLED, ESCALATED, RECOVERY) with 22+ valid transitions, 7 explicit invalid, deterministic rejection via `scripts/state_machine.sh` + `config/state_machine.yaml` - 37 tests PASS
- **Run Manager:** Unique RUN-YYYY-XXXXXX ID, isolated dir `.eng/runs/RUN-xxx/` with manifest.json, state.json, events.jsonl, decisions.jsonl, artifacts/, agents/, checkpoints/, verification/, receipt.json via `scripts/run_manager.sh`
- **Event Log:** Append-only `events.jsonl` with 23+ types (RUN_CREATED, BASELINE_STARTED, GATE_PASSED, etc.) via `scripts/event_log.sh`, no secrets
- **Agent Contracts:** 6 agents in `agents/*.yaml` (architect, worker, reviewer, security-reviewer, verifier, release-manager) with inputs/outputs/capabilities/permissions/tools/model_policy/delegation/termination/failure_policy/evidence_required
- **Permission Matrix:** Least privilege in `config/permissions.yaml` with 8 types (filesystem, shell, network, git, dependency, database, deployment, secret), enforced via `scripts/permission_check.sh`, no secret.read except human - 21 tests PASS
- **Model Routing:** Tier != Model separation in `config/model_policy.yaml`, low/medium/high reasoning, adapters in `adapters/` (claude, codex, copilot, generic), provider-independent core
- **Playbook Engine:** 11 workflow types in `workflows/` (feature, bug-fix, refactor, migration, performance, security, investigation, testing, release, documentation, incident) + 4 domain overlays in `domains/` (wordpress, android, web, backend) + risk overlays, composition via `scripts/playbook_engine.sh` - 7 tests PASS
- **Preview Mode:** `scripts/preview.sh` and `scripts/eng.sh preview` shows classification without mutation, no files mutated - 2 tests
- **Recovery System:** `scripts/recovery.sh` with detect, inspect, reconcile, recover, resume; checks uncommitted changes, branch divergence, checkpoint age; never destroys user changes - 8 tests PASS
- **Worktree Isolation:** `scripts/worktree.sh` creates isolated worktree per run at `.eng/runs/RUN/worktree`, detects conflicts, never auto-destroy
- **Review/Rework Bounded Loop:** Formal states REVIEW->REWORK->VALIDATION loop with max 2 cycles, then ESCALATED, no infinite loop
- **Receipt:** `scripts/receipt.sh` generates machine-readable receipt.json answering why tier/agents/gates selected, tools used, permissions, evidence, rework cycles, human approval
- **Structured Knowledge:** `.eng/knowledge/` with lessons/, failures/, decisions/, patterns/, regressions/, controlled promotion (freq>=3 or 1 CRITICAL)
- **Skill Registry:** `scripts/skill_registry.sh` with discover, inspect, validate, load, disable, manifest validation, permission checks, no auto remote exec
- **Adapter Layer:** `adapters/` with generic (always available), claude, codex, copilot (placeholder), provider-independent
- **Evaluation Expansion:** From 15 to 50 deterministic scenarios in `evals/scenarios_v1_1.md` covering routing (5), delegation (5), security (5), recovery (6), verification (5), governance (5), additional v1.1 (9) - target 50 met
- **Docs:** 10 new docs in `docs/` covering architecture, state-machine, agents, workflows, security, recovery, evaluation, adapters, audit
- **Control Plane CLI:** `scripts/eng.sh` main entry with preview, run, list, show, state, event, recover, worktree, receipt, registry, playbook, gate commands
- **Tests:** New tests 73 PASS (state_machine 37, permissions 21, recovery 8, playbook 7) + existing 15 = 88 total PASS
- **Audit:** `docs/audit/v1.1-baseline.md` and `docs/audit/v1.1-implementation-audit.md` with full before/after, tests, security, recovery, limitations, next steps

### Added - Phase B Completion (Full Update)
- **CI Full Suite:** `.github/workflows/test.yml` now runs all 5 test suites (gates 15, state_machine 37, permissions 21, recovery 8, playbook 7) + eval runner 122 scenarios + secret_scan + dep_audit + permission checks + preview no mutation + run manager + receipt + playbook engine + skill registry + no secrets check
- **Domain Expansion:** 11 new domain overlays in `domains/` (woocommerce, minecraft, paper, typescript, javascript, python, rust, game-development, cli, frontend, database) - total 15 domains (4 previous + 11 new), all with detection files/keywords, overlays lenses/checks/playbook_base, risk_modifiers
- **Adapter Implementation:** Real execution logic in `adapters/generic/adapter.py` (GenericAdapter with load_agent_contract, check_permission, translate_model_policy, translate_workflow_state, execute_tool, dispatch_agent, event logging, cost tracking), `adapters/claude/adapter.py` (ClaudeAdapter with model_mapping haiku/sonnet/opus), `adapters/codex/adapter.py` (CodexAdapter gpt-4o-mini/gpt-4o/o1)
- **Cost Telemetry:** `scripts/cost_telemetry.sh` with record --run RUN --metric NAME --value VAL (metrics: agent_count, model_usage, execution_duration, tool_calls, review_cycles, rework_cycles, tokens, cost), show --run RUN, optional via ENG_TELEMETRY=1, provider-independent, updates state.json budget.tokens_used_est, agent_count, tool_calls, review_cycles, estimated_cost
- **Knowledge Promotion Automation:** `scripts/knowledge.sh` with add --id L-XXX --category CAT --trigger TRIG --failure FAIL --root-cause RC --correction CORR --evidence EV --applicable-when WHEN --confidence high|medium|low, validate FILE (checks required fields id/category/trigger/failure/root_cause/correction/evidence/applicable_when/confidence/created/last_verified), promote-check --id ID (freq>=3 or CRITICAL or high confidence -> PROMOTE, requires human approval if changes hard rules), list, check ACTOR (only human/architect can propose, others DENY - no free modification of trusted knowledge)
- **Evaluation Runner:** `evals/run_all.sh` runs all 88 unit tests + 34 simulated deterministic scenarios = 122 total, generates `evals/results/v1.1-evaluation-report.md` with breakdown per category, pass rate, evidence logs, backward compat, security, determinism
- **Worktree Cleanup:** `scripts/worktree.sh` now has cleanup --older-than 7d [--dry-run] - finds old terminal runs (COMPLETED/FAILED/CANCELLED/BLOCKED) older than threshold via find -mtime, dry-run shows would cleanup, actual removes worktree and checkpoints, keeps receipt and manifest per retention policy
- **Receipt Enrichment:** `scripts/receipt.sh` now includes why_workflow_selected, why_domain_selected, why_risk_selected, cost_breakdown (token_budget, tokens_used_est, agent_count, tool_calls, review_cycles, estimated_cost) in routing section, plus final section with why_agents_selected, which_tools_used, which_permissions_granted, etc.

### Changed
- SKILL.md: 81 -> 94 lines, version 1.0.1 -> 1.1.0, added control plane concepts, file map updated, still under 150
- README.md: polished with badges, v1.1.0 file tree (config, agents, workflows, domains, adapters, scripts control plane + gates, docs, .eng/knowledge, tests 88), quick start with eng.sh, exit code table, structured findings docs
- .gitignore: updated to ignore .eng/runs/, .eng/evidence.md, .eng/state.json, keep knowledge and templates
- scripts/receipt.sh: enriched with workflow/domain/risk reasons and cost breakdown
- scripts/worktree.sh: added cleanup with retention policy
- tests/: fixed pipefail handling (grep -E, || true, output capture) for state_machine, permissions, recovery, playbook - all 88 PASS
- evals/: added run_all.sh and v1.1-evaluation-report.md generation

### Fixed
- knowledge.sh validate bug: $2 -> $1 after shift
- recovery.test.sh and playbook.test.sh: grep -q with | literal -> grep -Eq, plus pipefail handling
- permission_check.sh: reviewer shell restricted should DENY bash, now only execute allows bash
- secret_scan.sh: fixed pipe subshell FOUND loss, excludes tests/
- GitHub push protection: changed Stripe key test to SECRET_KEY pattern
- .gitignore: updated to ignore .eng/runs/, .eng/evidence.md, .eng/state.json, keep knowledge

### Preserved (Backward Compatibility)
- Existing commands: detect_env, baseline, gate_check, secret_scan, dep_audit, report_lint, gates.test.sh
- Existing playbooks: references/playbooks/ 6 files
- Existing lenses: references/lenses/ 7 files
- Existing tests: gates.test.sh 15 PASS
- Gate hardening from v1.0.1: no state.json trust, EXIT_CODE logs, structured findings
- No breaking changes, all additive

## 1.0.1 - 2026-09-29
### Fixed - Gate Hardening (per bugfix guide)
- **Rule**: No gate reads state.json for PASS, only real command outputs (fixes False Completion)
- **lib_run.sh**: New shared library with `run_step <phase> <name> <cmd>` producing `.eng/artifacts/<phase>_<name>.log` with `EXIT_CODE=<n>` last line, plus `detect_cmds`, `get_exit`, `file_sha256`
- **G0 Build**: Now re-executes build via `run_step current build` and checks `current_build.log` EXIT_CODE. Removed state.json read. Returns NOT_APPLICABLE if no build command, NOT TESTED if no log, FAIL if exit !=0. No longer PASS on broken build.
- **G1 Tests**: Fixed to use `baseline_test.log` and `current_test.log` with EXIT_CODE. Implements regression check: if baseline exit 0 and current !=0 => FAIL. If no TEST_CMD => NOT TESTED. Previously searched for `*test*.log` that no script produced.
- **G2 Lens**: Structured finding format enforced: `- [F-XXX] severity=HIGH|CRITICAL|MED|LOW status=OPEN|CLOSED | description`. Gate now order-independent: greps for `severity=(high|critical)` and `status=open` separately. Fixes CLOSED flagged as FAIL and reversed order missed.
- **G3 Security**:
  - secret_scan.sh: Fixed exit code bug due to pipe subshell variable loss. Now uses temp file and re-parses FOUND. Excludes `tests/` dir to avoid self-detection. Exit 1 on secret, 0 clean.
  - dep_audit.sh: Distinguishes tool error vs vuln. If no lockfile (package.json without package-lock.json) => NOT TESTED exit 2 with message "no lockfile". If audit JSON parse error => NOT TESTED. Only high+critical count => FAIL. Returns NOT APPLICABLE (exit 3) if no manifest.
  - gate_check.sh G3: Now requires both secret_scan.log and dep_audit.log. Missing => NOT TESTED. NOT TESTED in either log => NOT TESTED. FAIL in either => FAIL.
- **G4 Release**: Now verifies real sha256 hash calculated from artifact via `file_sha256`, not just string presence. Checks `sha256:[a-f0-9]{64}` pattern and optionally verifies against file.
- **report_lint.sh**: Added structured findings format warnings. Warns if review files contain severity/status lines not in `- [F-XXX]` format. Still PASS with warnings, FAIL on hallucinated claims or SOLVED without evidence.
- **lessons.md**: Separated EXAMPLE (fictional) label, fixed wording "baseline as gate G0" -> clarified G0=Build, baseline is pre-step.
- **evals/**: Added 4 real executed scenarios with with/without comparison in `evals/results/` (S1, S2, S8, S9). Proves tier selection, honest NOT TESTED, no state.json trust.
- **tests/gates.test.sh**: Added 10 regression fixtures T1-T10 covering build healthy/failing, state.json trust attack, review CLOSED/OPEN order, secret planted, missing logs, no lockfile, SOLVED empty evidence. All 15 assertions PASS.
- **CI**: Added `.github/workflows/test.yml` to run gate tests on push/PR.

### Changed
- All lenses updated to document structured finding format
- Examples updated to new format
- secret_scan excludes tests/ to avoid self-pollution

## 1.0.0 - 2026-09-29
- Initial release
- Implements mother skill with Tier 0-3 system
- Adds 7 lenses (security, testing, performance, ux, docs, architecture, release)
- Adds 6 playbooks (web-api-backend, wordpress-woocommerce, minecraft-paper-plugin, android, game-engine-typescript, cli-tool)
- Adds 6 executable scripts (detect_env, baseline, secret_scan, dep_audit, gate_check, report_lint)
- Adds state format v1 with .eng/ persistence
- Adds evidence rules with SOLVED/UNSOLVED/BLOCKED/NOT TESTED/NOT APPLICABLE/ASSUMED
- Adds failure modes with detection/mitigation for 13 modes
- Adds interaction protocol with 3-question limit and approval points
- Adds evals with 15 scenarios and with_vs_without comparison
- Adds examples good vs bad for plan, verify, review
- Enforces hard rules: evidence over claims, independent verification, anti-sycophancy, loop caps (2 per gate), token budgets, executable gates

## Versioning Note
- MAJOR: breaking change in SKILL.md or state.json schema or gate definitions
- MINOR: new lens, playbook, or script feature backward compatible
- PATCH: docs, bugfix, examples
- State.json has its own version field (1.0.0) for migration. If mismatch, agent must migrate or mark BLOCKED.
