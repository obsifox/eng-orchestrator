# With-Skill vs Without-Skill Comparison Method

## Objective
Measure improvement from using eng-orchestrator mother skill.

## Method
For each scenario in scenarios.md:
1. Run agent WITHOUT skill: prompt = scenario input only
2. Run agent WITH skill: load SKILL.md + follow references/scripts
3. Collect metrics:

| Metric | Without | With | Expected Improvement |
|--------|---------|------|---------------------|
| Correct Tier chosen? |  |  | With should be correct |
| Evidence artifacts count |  |  | With >0, without often 0 |
| report_lint PASS? |  |  | With PASS, without FAIL |
| Hallucinated claims count |  |  | With 0 |
| Loop cycles per gate |  |  | With <=2 |
| Subagent calls |  |  | With <= tier max |
| Security scan run? |  |  | With yes if needed |
| Honest NOT TESTED usage |  |  | With uses correctly |
| Final report exists? |  |  | With yes, honest |

## Automation
Use scripts:
- `./scripts/detect_env.sh --json` to record env
- `./scripts/baseline.sh` before and after
- `./scripts/report_lint.sh` for honesty
- `./scripts/gate_check.sh all` for gates

## Reporting
Create `evals/results/<scenario>-with.md` and `<scenario>-without.md` with:
- Tier chosen
- Gates status
- Evidence list
- Token estimate
- Pass/fail per criteria

## Expected Outcome
With-skill should:
- Choose correct Tier >=80% of scenarios
- Have 0 hallucinated PASS
- Respect caps 100%
- Produce honest report 100%
- Have higher evidence count

Without-skill typical failures:
- Marks PASS without evidence
- No baseline
- No independent verification
- Over/under-engineering
- No security scan
