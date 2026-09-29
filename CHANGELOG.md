# Changelog

All notable changes to eng-orchestrator skill.

## 1.0.0 - 2026-09-29
- Initial production release
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
