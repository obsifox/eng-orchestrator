# Lens: Release

## When to Load
Tier 2+ if artifact to deliver, Tier 3 always.

## Checklist
- [ ] Build artifact exists and matches reviewed source (checksum)
- [ ] Version bumped per CHANGELOG.md
- [ ] No secrets in artifact
- [ ] Artifact size reasonable
- [ ] Release notes drafted
- [ ] Installation / deployment tested or marked NOT TESTED
- [ ] Rollback plan

## Expected Output
- `.eng/artifacts/release-review.md`:
  - Artifact path + sha256
  - Build command log
  - Verdict
- Release notes file

## Tools
- Build commands
- `sha256sum` artifact
- `scripts/gate_check.sh release`

## Gate Condition
G4: artifact exists AND hash logged in evidence.md AND hash matches reviewed source diff. If no artifact needed, NOT_APPLICABLE with justification.
