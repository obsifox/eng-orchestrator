# S2 CLI Calculator - WITH Skill

## Input
Create CLI tool that adds two numbers, with --help

## Execution
- Tier: 1 (20-200 LOC, 1-3 files)
- Brief: CLI tool, domains cli, security (no secrets)
- Plan: T1 implement cli, T2 testing, file-disjoint check
- Baseline: no existing code -> baseline_build NOT APPLICABLE, baseline_test NOT APPLICABLE
- Build: npm run build if present else node check
- Tests: created test file, run via `npm test` -> current_test.log EXIT_CODE=0
- Lenses: testing (mandatory)
- Gates:
  - G0: PASS (build exit 0)
  - G1: PASS (current test exit 0, baseline NA -> pass)
  - G2: PASS (no HIGH OPEN, review file with structured findings clean)
  - G3: secret_scan PASS, dep_audit NOT TESTED (no lockfile) -> G3 NOT TESTED (honest)
- Evidence: baseline logs, current logs with EXIT_CODE, testing-review.md with structured format
- Verifier: fresh context, saw only brief + diff + logs, ran gate_check --no-run PASS

## Pass Criteria
- Tier 1 correct ✅
- Plan light exists ✅
- Testing lens loaded ✅
- Baseline run ✅
- Tests log with EXIT_CODE ✅
- Verifier log exists ✅
- No state.json trust ✅
