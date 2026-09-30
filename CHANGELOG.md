# Changelog

All notable changes to eng-orchestrator skill.

## 2.3.1 - 2026-09-30
### Added - Platform persistence and recovery
- **`platform/core/storage.py`:** Profiles, settings and diagnostic exports now live on disk in the layout the roadmap specifies (section 39): `profiles/index.json`, `profiles/<identifier>.json`, `settings/settings.json`, `diagnostics/`. Imported profiles, the active profile and saved reports survive a restart.
- **Atomic writes:** a file is serialised to a temporary in the destination directory and renamed over the target, so a process that dies mid-write leaves the previous file intact rather than a truncated one.
- **Quarantine rather than silence:** a file that cannot be parsed, fails validation, or carries a checksum that does not match its contents is renamed with a reason and a timestamp, reported in the load result, and the application still starts.
- **Path building refuses to leave the root:** an identifier is validated and the resolved path is checked against the profiles directory, because the boundary that turns a string into a path should not depend on a validator elsewhere remaining correct.
- **Settings:** active profile, redaction level and interface state, merged rather than replaced so a write of one section does not discard another.
- **New API routes:** `POST /api/profiles/activate`, `POST /api/settings`, `GET /api/diagnostics/list`, and `persist=true` on `GET /api/diagnostics` to write a report to disk. Deleting the active profile is refused, so the environment is never left undefined.
- **Interface:** an active-profile selector with activate and delete, a storage panel showing the directory, whether writes reach the disk, and anything quarantined on load, and a saved-exports table.
- **Tests:** 16 storage tests added, suite total 100.

### Fixed during development
- **`storage.load()` did not catch a tampered profile file.** It compared the profile's checksum after `GeoProfile.from_payload` had already resealed it, so the comparison was between two freshly computed values and always agreed. Payloads now go through `ProfileStore.import_payload`, which is the same path an untrusted paste takes, so there is one validation path rather than two that can disagree.
- **Settings on disk were ignored at start-up.** `PlatformStorage.__init__` created the directories but never read `settings.json`, so a restart lost the active profile.
- **Diagnostic exports overwrote each other.** Filenames were built from a one-second timestamp with digits stripped from the label, so several exports inside the same second resolved to one name and all but the last were lost.
- **The shipped `default` profile used a reserved identifier.** `validate_identifier` reserves `default`, so the profile could not survive a round trip through its own schema. It is now `default-environment`; the reservation is unchanged, because a user profile should not be able to shadow the name the application falls back to.

### Notes
- Performance has still not been measured. Stage timings are recorded per resolution and shown in the interface, which is what a benchmark would need, but no benchmark has been run and no performance claim is made.

## 2.3.0 - 2026-09-30
### Added - Browser Platform: Environment Core
- **`platform/`:** A working implementation of the environment resolution layer the browser platform roadmap describes, plus a control center interface. Dependency-free, standard library only, no build step and no lockfile.
- **Geo engine (`core/geo.py`):** Five providers (physical, virtual, automatic, hybrid, disabled) each declaring its own source and confidence. Radius sampling is uniform over the disc by sampling `R * sqrt(u)`, verified against 1500 samples with a mean at two thirds of the radius. Randomization modes: none, stable, session, dynamic, seeded.
- **Timezone engine (`core/timezone_engine.py`):** Identifiers validated against the local tz database through `zoneinfo`, with offsets and daylight-saving state at a stated instant, plus a regional plausibility check for diagnostics. Case-insensitive identifier resolution, because the database contains no two identifiers differing only by case.
- **Locale engine (`core/locale_engine.py`):** Keeps five surfaces apart - browser locale, language preference, HTTP language, JavaScript locale, system locale. BCP-47 validation with a documented restriction of the primary subtag to two or three letters. Accept-Language construction with quality decay that never reaches zero.
- **DNS engine (`core/dns_engine.py`):** Browser-scoped resolution plans for system, custom, DoH and DoT. Endpoints must be HTTPS, ports and addresses are validated, and every plan reports its fallback with the consequence stated. The module imports no networking library and holds no file handle, so it cannot modify the operating system, and a test asserts that for all four modes.
- **Profile engine (`core/profiles.py`):** Schema v3 with a migration path from v1 and v2, checksums computed on construction, strict unknown-field rejection, reserved identifiers, and import validation before activation. A checksum proves a file is intact, not that it is safe, and a profile from a newer schema is refused rather than interpreted.
- **Pipeline (`core/environment.py`):** Ten named stages, each timed and recorded with status, output, provenance and notes. A failing stage stops the pipeline and names itself. Per-site policy precedence is total: origin beats subdomain beats domain, then longer patterns win.
- **Diagnostics (`core/diagnostics.py`):** Consistency analysis across geolocation, timezone, locale, language, DNS and network, with the surfaces it does not control listed explicitly. Three redaction levels, defaulting to redacted, with credential-shaped values removed at every level.
- **Host and detector (`core/host.py`):** Reads host signals without probing the network. Automatic detection returns a country centroid with a country-sized radius and a low confidence, because a timezone identifies a band of the globe and not a position within it.
- **Server (`server.py`):** Standard library HTTP server on one origin, so the interface never calls localhost and never needs a cross-origin exception. Bound to 0.0.0.0 so the preview host can reach it.
- **Interface (`ui/`):** Control center with ten panels covering the current environment, location, timezone, locale, network, DNS, the privacy dashboard, profiles, per-site rules and diagnostics. No build step, no framework.
- **Tests:** 84 unit tests, all passing.
- **Content policy:** `platform/policy.yaml` is enforced over the application source by the v2.2 scanner. The source reports 0 findings across 20 files on all four rules.

### Fixed during development
- `GeoProfile` could be constructed without a checksum, which made `verify_checksum` meaningless for every profile built in code rather than imported. Sealing now happens on construction.
- `normalise_language_tag` accepted a leading or trailing dash, so `-en` resolved to `en`.
- `is_valid_identifier` rejected `utc`, because the tz database lookup is case sensitive while the database contains no two identifiers differing only by case.
- `VirtualProvider` reported a seed for a zero-radius area, implying randomization that had not happened.

### Notes
- The application does not claim to be a browser. It resolves what a browser should present and produces a descriptor; it does not render content and it does not contain a browser engine.
- The consistency report is diagnostics, not a guarantee. It states what it examined and names canvas, WebGL, audio, fonts and screen metrics as surfaces it does not control and therefore cannot report on.
- No performance claim is made here. Stage timings are recorded per resolution and visible in the interface, which is what a repeated benchmark would need, but no benchmark has been run.

## 2.2.0 - 2026-09-30
### Added - Content Policy Enforcement + G6_Policy Gate
- **`scripts/policy_scan.py`:** Enforces `.eng/policy.yaml` across four rules - `comments` (forbidden comment markers), `emoji`, `language` (non-permitted writing systems) and `branding` (prohibited organisation strings outside allow paths). Dependency-free, reuses the YAML subset parser from `project_profile.py`.
- **Language-aware comment lexer:** The comment rule is a lexer, not a grep. Each dialect declares which markers it actually has (javascript/typescript/c/cpp/rust/go/java/csharp/kotlin/swift/scala/dart/php/gradle = `//` + `/* */`, rust/swift/scala nest, css = `/* */` only, scss/sass/less/jsonc = both, sql = `--` + `/* */`, python/ruby/shell/yaml/toml/ini/r/makefile/dockerfile = `#`). Strings, template literals and regular expression literals are consumed before any marker is reported, so `https://example.com`, `/^https?:\/\/x$/`, `width / 2` and Python `total // count` are never findings. Regex-vs-division uses the standard preceding-token heuristic; its failure mode is a missed finding, never a fabricated one.
- **Emoji rule:** Pictographic blocks U+1F000-U+1FAFF, U+2600-U+27BF, U+2B00-U+2BFF, U+2300-U+23FF, the emoji variation selector U+FE0F and the individual emoji-presentation codepoints. Copyright, registered and trade mark signs, arrows and geometric shapes stay out of the core set because license files and architecture diagrams legitimately use them; `emoji.extended: true` adds them.
- **Language rule:** 29 writing systems by codepoint range (Arabic, Hebrew, Cyrillic, Greek, CJK, Hiragana, Katakana, Hangul, Thai, Devanagari, Armenian, Georgian, Khmer, Lao, Myanmar, Tamil, Telugu, Bengali, Gujarati, Gurmukhi, Kannada, Malayalam, Sinhala, Ethiopic, Tibetan, Mongolian, Cherokee, Syriac, Thaana). `forbid_accented_latin` adds Latin-1 Supplement and Latin Extended-A. Documented honestly as a script check, not a language check: ASCII German and Dutch are not detectable this way.
- **Branding rule:** Case-insensitive substring matching by default, optional word boundaries, `allow_paths` globs for legal attribution.
- **`scripts/policy_scan.sh`:** Wrapper writing `.eng/artifacts/policy_scan.log` with a `RESULT:` line and trailing `EXIT_CODE=`, the contract `gate_check.sh` reads.
- **`G6_Policy` gate:** Part of `gate_check.sh all`. NOT APPLICABLE when `.eng/policy.yaml` is absent - a repository that never adopted a content policy is not failing one, and NOT APPLICABLE does not drag the overall verdict down.
- **Exit codes:** 0 PASS, 1 violations, 3 NOT APPLICABLE, 4 empty config, 5 malformed config or unknown marker/script name, 6 internal error.
- **Config:** `.eng/templates/policy.yaml` template, `examples/browser-platform.policy.yaml` filled-in example, `examples/browser-platform.project.yaml`.
- **Fixtures:** `tests/fixtures/policy/dirty/` and `clean/` prove both directions - a URL, a regex literal, division, CSS `//` and Python floor division must not be reported, while a JS line comment, a JS block comment, a CSS block comment, a nested Rust block comment, a hash comment under a hash policy, emoji, four writing systems and a case-varied brand string must all be reported.
- **Tests:** `tests/policy_scan.test.sh`, 34 asserts. Suite total 137 -> 171 across 9 suites.
- **Docs:** `docs/security/policy-scan.md` covering the dialect table, the regex heuristic and its failure mode, the emoji ranges, the language rule's limits, exit codes and the gate contract.
- **CI:** Three new steps - policy scan tests, template and example validation, and the dirty/clean fixture matrix asserting exit 1 and exit 0 respectively.

### Fixed
- `as_list` in `policy_scan.py` normalises an absent key, an empty mapping and an empty sequence to "nothing configured". Without this, an empty `include:` key parsed to `{}`, became a one-element glob list matching no file, and a scan of zero files would have reported PASS.
- `scan_comments` had the block-comment span duplicated across the forbidden and not-forbidden branches. The span is now scanned once and only the reporting is conditional, so the two paths cannot drift. Behaviour is unchanged and covered by P11 (nested Rust block comment is one finding) and P13.

### Notes
- `eng-orchestrator` does not adopt `.eng/policy.yaml`. This repository uses `#` comments, pictographs in test output and documentation, Persian trigger phrases in `SKILL.md` and the organisation name in GitHub URLs. Applying the browser platform example policy to this tree yields 374 findings across 198 files, none of which is a defect here. The scanner is a tool a project adopts, not a rule the tool imposes.
- CI installs `pyyaml` for other suites; `policy_scan.py` itself has no third-party dependency and runs on a bare `python3`.

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
