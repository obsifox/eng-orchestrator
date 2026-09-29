# Changelog

All notable changes to eng-orchestrator skill.

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
