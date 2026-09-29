# Changelog

All notable changes to eng-orchestrator skill.

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

### Changed
- SKILL.md: 81 -> 94 lines, version 1.0.1 -> 1.1.0, added control plane concepts, file map updated, still under 150
- README.md: polished with badges, v1.1 features, file tree updated, exit code table, structured findings docs
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
