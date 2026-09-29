# Lens: Testing

## When to Load
Tier 1+ mandatory. Tier 0 optional but recommended if test runner exists.

## Checklist
- [ ] Baseline tests run and recorded
- [ ] New code has tests proportional to Tier (Tier1: at least happy path, Tier2: edge cases, Tier3: regression + integration)
- [ ] Tests are independent, not flaky
- [ ] No test that only asserts true
- [ ] Tests actually run (log exists)
- [ ] Coverage not claimed without measurement
- [ ] Regression tests for bugfixes

## Expected Output
- `.eng/artifacts/testing-review.md`:
  - Baseline: X pass / Y fail
  - After: X' pass / Y' fail
  - New tests list
  - Findings
  - Verdict
- Log file from test runner in artifacts/

## Tools
- `scripts/baseline.sh`
- Project test command (npm test, pytest, etc)

## Gate Condition
G1: tests >= baseline AND no new failures. If no runner, NOT TESTED with reason.

## Anti-Sycophancy
Must show command output. Cannot say "tests pass" without log path.
