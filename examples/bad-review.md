# Bad Review Example

## Review (BAD)

"As a Security Guru with 20 years experience, I have reviewed this code thoroughly. It is secure, no issues. PASS. Good job!"

## Why BAD
- Persona theater: "Security Guru with 20 years"
- No files listed, no lines
- No concrete checks: what authz? what input validation?
- No tool used (secret_scan not run)
- Sycophantic, no findings, no proof of checking
- Should explicitly list what checked and found clean if clean: e.g. "Checked: authz on 3 endpoints, input validation on 5 inputs, secret_scan exit 0 - clean"
