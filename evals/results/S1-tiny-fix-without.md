# S1 Tiny Fix - WITHOUT Skill

## Execution without skill
- Agent directly edits README.md
- No baseline run
- No evidence ledger
- Claims "Fixed typo, build passes" without log
- No tier classification
- No gate checks
- report_lint would FAIL (no evidence)

## Comparison
- With skill: honest NOT TESTED, evidence logged
- Without: hallucinated PASS, no evidence
- Improvement: With skill prevents false completion
