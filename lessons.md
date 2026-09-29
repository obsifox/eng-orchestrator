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

## EXAMPLE (fictional) - Do not count as real lesson
## L-001 - EXAMPLE (fictional): Forgetting baseline before change
- Date: 2026-09-20
- Project: api-refactor-example
- Tier: 2
- Failure Mode: Context Drift / Regression not detected
- What happened: Changed DB layer without baseline tests, broke existing flow
- Root cause: Skipped baseline.sh
- Mitigation: Enforced baseline.sh as mandatory pre-step before G0 Build (G0 = Build, not baseline itself)
- Frequency: 2
- Proposed: Make gate_check.sh fail G0 if baseline_build.log missing
- Status: PROMOTED in v1.0.0 - baseline.sh now creates baseline_build.log with EXIT_CODE

## Current Lessons
- (Add new lessons after each project below this line)
