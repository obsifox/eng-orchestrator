# Lessons Learned - Promotion Mechanism

## Purpose
After each project, agent records recurring mistakes to improve skill over time.

## Format
```
## L-001 - Title
- Date: ISO8601
- Project: name
- Tier: 0-3
- Failure Mode: e.g. False Completion
- What happened:
- Root cause:
- Mitigation applied:
- Frequency: 1
- Proposed skill change: e.g. Add check in gate_check.sh
- Status: PROPOSED / PROMOTED / REJECTED
```

## Promotion Rule
- Frequency >=3 across different projects OR 1 CRITICAL failure -> Promote to skill
- Promotion means: update relevant file (SKILL.md, lens, script, reference) and add entry to CHANGELOG.md
- Must have evidence: link to 3 evidence.md files showing same issue
- User approval required for promotion if changes SKILL.md hard rules

## Examples
## L-001 - Forgetting baseline before change
- Date: 2026-09-20
- Project: api-refactor
- Tier: 2
- Failure Mode: Context Drift / Regression not detected
- What happened: Changed DB layer without baseline tests, broke existing flow
- Root cause: Skipped baseline.sh
- Mitigation: Enforced baseline as mandatory gate G0
- Frequency: 2
- Proposed: Make baseline.sh fail gate if not run
- Status: PROMOTED in v1.0.0

## Current Lessons
- (Add new lessons after each project)
