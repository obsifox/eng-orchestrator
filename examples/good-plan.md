# Good Plan Example (Tier 2)

## Project: WooCommerce Bulk Discount
Tier: 2 | Domains: wordpress, php, js, security

## Task Graph
- T1: Discovery - Read existing plugin structure, record in brief.md
  - Owner: architecture lens
  - Evidence: file list log .eng/artifacts/T1.log
  - Depends: none
- T2: Architecture note - Decide hook placement, DB: use wp_options not custom table (justified)
  - Owner: architecture
  - Depends: T1
  - Output: decisions.md ADR-1
- T3: Backend - Implement discount calculation, nonce + capability check
  - Owner: security lens review required
  - Depends: T2
  - Acceptance: discount applies for qty>=10, unit test pass, evidence .eng/artifacts/T3.log
- T4: Frontend - JS for admin UI, enqueue only on product page
  - Owner: ux lens
  - Depends: T2
  - File-disjoint from T3 (different files)
- T5: Testing - Integration test activate plugin, apply discount
  - Owner: testing lens
  - Depends: T3,T4
  - Evidence: npm test log
- T6: Security review
  - Owner: security lens
  - Depends: T3,T4
  - Output: .eng/artifacts/security-review.md

## Dependencies
T1 -> T2 -> T3,T4 (parallel file-disjoint) -> T5,T6

## Risks
R1: Existing coupon logic conflict - MED - Mitigation: check existing hooks, test
R2: Performance - options autoload - LOW - Use transient

## Scope Control
REQUIRED: bulk discount calculation, admin UI, nonce
BACKLOG: variable product support, REST API

## Budget
Tokens est 80k / 150k budget, subagents max 3, cycles 2 per gate
