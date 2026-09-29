# Good Review Example (Security Lens)

## Files Checked
- includes/class-discount.php:1-200
- includes/class-admin.php:30-90
- assets/js/admin.js
- Ran secret_scan.sh log .eng/artifacts/secret_scan.log

## Findings
[HIGH] includes/class-discount.php:78 - $_POST['discount'] used without sanitization. Fix: sanitize_text_field + intval check. REQUIRED-FOR-ACCEPTANCE
[MED] includes/class-admin.php:45 - capability check missing on AJAX handler. Add current_user_can('manage_woocommerce'). REQUIRED
[LOW] assets/js/admin.js:12 - no error handling for AJAX failure. BACKLOG

## Remediation
- Fix HIGH and MED, re-run secret_scan, update evidence.md

## Verdict
FAIL - 1 HIGH open, must fix before G2 PASS

## Evidence
- secret_scan.log exit 0 but manual finding HIGH
- File hashes logged in evidence.md
