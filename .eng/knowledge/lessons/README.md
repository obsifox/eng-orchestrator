# Knowledge - Lessons

Structured lessons with promotion control.

Format:
```yaml
id: L-001
category: security
trigger: "When handling auth"
failure: "Forgot capability check"
root_cause: "Missing current_user_can"
correction: "Add capability check per playbook"
evidence: ".eng/runs/RUN-xxx/security-review.md"
applicable_when: "WordPress AJAX handlers"
confidence: high
created: 2026-09-29
last_verified: 2026-09-29
```

Promotion: frequency >=3 or 1 CRITICAL -> promote to skill, requires evidence links.
Agents must NOT freely modify trusted knowledge.
