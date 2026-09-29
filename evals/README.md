# Evals - 15 Scenarios

This folder tests whether the mother skill correctly chooses Tier, enforces evidence, respects caps, and produces honest reports.

## How to Run
For each scenario, run agent with skill and without skill, compare:

- Tier chosen vs expected
- Evidence artifacts exist?
- Loop caps respected?
- Report honesty (no hallucinated PASS)
- Token use estimate

Pass criteria defined in scenarios.md.

## With vs Without Skill
See with_vs_without.md for comparison method.
