# Bad Verification Report (Anti-Pattern)

## Verification (BAD)

"I reviewed the code and it looks great! Highly performant, secure, production-ready. Tests pass. No issues found. PASS"

## Why BAD
- No evidence refs, no logs
- No fresh context - mentions chat history
- Hallucinated: "highly performant" without benchmark
- Claims "Tests pass" without log path or count
- No concrete files checked listed
- No gate_check command run
- Sycophantic: generic praise, no concrete findings
- Should be: list what checked and found clean, or list findings with file:line
