# Good Review Example (Security Lens) - Structured Format v1.0.1

## Files Checked
- includes/class-discount.php:1-200
- includes/class-admin.php:30-90
- assets/js/admin.js
- Ran secret_scan.sh log .eng/artifacts/secret_scan.log exit 0
- Ran dep_audit.sh log .eng/artifacts/dep_audit.log exit 0

## Findings (structured - order independent)
- [F-001] severity=HIGH status=OPEN | $_POST['discount'] without sanitization | includes/class-discount.php:78 | REQUIRED-FOR-ACCEPTANCE
- [F-002] severity=MED status=OPEN | capability check missing on AJAX handler | includes/class-admin.php:45 | Add current_user_can('manage_woocommerce')
- [F-003] severity=LOW status=OPEN | no error handling for AJAX failure | assets/js/admin.js:12 | BACKLOG
- [F-004] severity=HIGH status=CLOSED | Fixed XSS via esc_html in commit abc | includes/class-discount.php:90

## Remediation
- Fix HIGH and MED OPEN, re-run secret_scan, update evidence.md
- CLOSED findings must reference fix commit

## Verdict
FAIL - 1 HIGH OPEN remains, must fix before G2 PASS

## Evidence
- secret_scan.log exit 0 log .eng/artifacts/secret_scan.log
- File hashes logged in evidence.md
- Gate check: `scripts/gate_check.sh G2_Lens --no-run` should FAIL due to F-001 OPEN HIGH
