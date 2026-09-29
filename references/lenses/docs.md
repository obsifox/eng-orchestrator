# Lens: Docs

## When to Load
Tier 1+ if public API, README, setup changed. Tier 2+ always minimal docs.

## Checklist
- [ ] README reflects actual implementation
- [ ] Setup instructions work (tested or NOT TESTED stated)
- [ ] Configuration documented
- [ ] API docs if API changed
- [ ] Changelog / migration notes if breaking change
- [ ] No outdated docs

## Expected Output
- `.eng/artifacts/docs-review.md`:
  - Docs checked
  - Findings (missing, outdated)
  - Verdict

## Tools
- Read docs, compare to code
- Try setup steps if feasible, log result

## Gate Condition
For Tier 2+, README and setup must be PASS or NOT TESTED with reason. No fabricated docs.
