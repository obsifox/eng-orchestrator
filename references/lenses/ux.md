# Lens: UX / UI

## When to Load
Any frontend, mobile, game UI, CLI UX, WordPress frontend, dashboard.

## Checklist
- [ ] Information architecture clear
- [ ] User flows (happy, error, empty, loading)
- [ ] Responsive / mobile behavior
- [ ] Accessibility (keyboard, ARIA, contrast) - at least checked
- [ ] Error states with actionable messages
- [ ] Empty states
- [ ] Loading states
- [ ] Consistency with existing UI
- [ ] No destructive action without confirmation

## Expected Output
- `.eng/artifacts/ux-review.md`:
  - Screens/flows checked
  - Findings: usability issues severity
  - Screenshots list if applicable (or description)
  - Verdict

## Tools
- Manual review
- Accessibility checklist (quick axe or manual)

## Gate Condition
No open HIGH UX issue that breaks core flow. MED/LOW -> BACKLOG allowed.

## Note
UX review must coordinate with engineering constraints logged in decisions.md.
