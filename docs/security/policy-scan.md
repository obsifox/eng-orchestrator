# Content Policy Enforcement

Status: implemented, v2.2
Owner: security-reviewer
Entry point: `scripts/policy_scan.py`, wrapped by `scripts/policy_scan.sh`
Gate: `G6_Policy` in `scripts/gate_check.sh`
Configuration: `.eng/policy.yaml`, template at `.eng/templates/policy.yaml`
Tests: `tests/policy_scan.test.sh`, 34 asserts

## Purpose

A content policy written as prose is not a control. A rule that says "no `//`
comments" and is enforced by nothing will be violated within a week, and the
violation will be invisible until a human reads the diff. This subsystem turns
four such rules into commands that exit non-zero.

| Rule | Question it answers |
| --- | --- |
| `comments` | Does the source contain comment markers this project forbids? |
| `emoji` | Do any files contain emoji or pictographs? |
| `language` | Do any files contain characters from writing systems the product does not use? |
| `branding` | Do prohibited organisation or product strings appear outside the permitted attribution paths? |

## Why the comment rule needs a lexer

The naive implementation is `grep -n '//'`. It reports every one of these as a
violation:

```javascript
const endpoint = "https://example.com/geo";
const scheme = /^https?:\/\/[a-z0-9.-]+$/;
const half = width / 2;
```

None of them is a comment. A scanner whose findings are mostly false stops being
read, and a control nobody reads is not a control. `policy_scan.py` therefore
tokenises each file: single-quoted, double-quoted and template strings, regular
expression literals, and block comment nesting are all consumed before any
marker is reported.

Each dialect declares only the markers it actually has:

| Dialect | line | block | hash | notes |
| --- | --- | --- | --- | --- |
| javascript, typescript, jsx, tsx | yes | yes | no | templates and regex literals tracked |
| c, cpp, objc, java, kotlin, csharp, go, dart, gradle | yes | yes | no | |
| rust, swift, scala | yes | yes | no | block comments nest |
| css | no | yes | no | `//` is not a CSS comment |
| scss, sass, less, jsonc | yes | yes | no | |
| php | yes | yes | yes | |
| sql | `--` | yes | no | |
| python, ruby, perl, shell, yaml, toml, ini, r, makefile, dockerfile | no | no | yes | |

Consequences that are deliberate, not accidents:

- A Python file containing `total // count` is never a finding under `slash_line`,
  because the Python dialect has no line marker. Floor division is not a comment.
- A CSS file containing `// legacy` is never a finding, because CSS has no line
  comment.
- A Rust file containing `/* outer /* inner */ still comment */` is one finding,
  not two, because Rust block comments nest.
- A `hash` marker is only ever a finding for a dialect that has one.

### Known limitation: regular expression detection

Deciding whether a `/` opens a regular expression or performs a division is
undecidable without a full parser. The scanner uses the standard heuristic: a `/`
starts a regex when the previous significant character cannot end an expression
(`(`, `,`, `=`, `:`, `[`, `!`, `&`, `|`, `?`, `{`, `}`, `;` and the arithmetic and
comparison operators), or when the previous token is a keyword that takes an
operand (`return`, `typeof`, `instanceof`, `in`, `of`, `new`, `delete`, `void`,
`throw`, `case`, `do`, `else`, `yield`, `await`).

The failure mode matters more than the failure rate. If a division is mistaken
for a regex, the scanner skips forward to the next `/` and reports nothing. It
does not fabricate a finding. A missed finding is recoverable at review; a stream
of false findings is not.

## Emoji detection

Core ranges cover the pictographic blocks: U+1F000 to U+1FAFF, U+2600 to U+27BF,
U+2B00 to U+2BFF, U+2300 to U+23FF, the emoji variation selector U+FE0F, and the
individual emoji-presentation codepoints U+203C, U+2049, U+2139, U+24C2, U+2934,
U+2935, U+3030, U+303D, U+3297 and U+3299.

The copyright sign U+00A9, the registered sign U+00AE, the trade mark sign
U+2122, arrows U+2190 to U+21FF and geometric shapes U+25A0 to U+25FF are
deliberately outside the core set. License files legitimately contain a
copyright sign, and architecture documents legitimately contain arrows. Setting
`emoji.extended: true` adds them.

## Language detection, and what it cannot do

The rule detects writing systems by codepoint range: Arabic, Hebrew, Cyrillic,
Greek, CJK, Hiragana, Katakana, Hangul, Thai, Devanagari, Armenian, Georgian,
Khmer, Lao, Myanmar, Tamil, Telugu, Bengali, Gujarati, Gurmukhi, Kannada,
Malayalam, Sinhala, Ethiopic, Tibetan, Mongolian, Cherokee, Syriac and Thaana.

This is a script check, not a language check, and the difference is worth stating
plainly. German, Dutch, Portuguese and Indonesian written in plain ASCII cannot
be detected this way. `forbid_accented_latin: true` adds Latin-1 Supplement and
Latin Extended-A, which catches most German and French text, at the cost of
flagging any legitimate accented proper noun.

Detecting natural language reliably needs a language model, which is a different
tool with a different failure profile. This scanner reports what it can prove and
does not claim the rest.

## Branding

`branding.prohibited` is a list of strings. Matching is case insensitive by
default, substring by default. `branding.allow_paths` is a list of globs where
attribution is permitted and everything else is a finding. The allow list should
stay narrow: legal notices, the about screen, the license file.

`word_boundary: true` requires the match not to be adjacent to a word character
or a hyphen, which prevents `ObsiFox` from matching inside a longer identifier.

## Configuration

```yaml
scope:
  include:
    - "application/**"
  exclude:
    - "**/.git/**"

comments:
  enabled: true
  forbid_markers:
    - slash_line
    - slash_block
  languages:
    - javascript
    - rust

emoji:
  enabled: true
  extended: false

language:
  enabled: true
  forbid_scripts:
    - arabic
    - cjk
  forbid_accented_latin: false

branding:
  enabled: true
  case_sensitive: false
  word_boundary: false
  prohibited:
    - Example Organisation
  allow_paths:
    - "docs/legal/**"
    - LICENSE
```

Semantics worth knowing:

- `include` absent or empty means every file that is not excluded. An include
  list containing an empty entry is normalised away rather than silently
  matching nothing, because a scan of zero files that reports PASS is worse than
  an error.
- `exclude` absent means the built-in default set: `.git`, `node_modules`,
  `.eng/runs`, `dist`, `build`, `target`, `out`, `__pycache__`, `.venv`,
  `.mypy_cache`, `.pytest_cache`.
- `comments.languages` absent means every known dialect.
- `language.forbid_scripts` absent means every known writing system.
- A rule with `enabled: false` is reported as SKIPPED, not as PASS with zero
  findings. The distinction is preserved in the log.
- Binary files are skipped by NUL detection in the first 8 KiB. Symlinks are not
  followed.

The YAML subset is the one `scripts/project_profile.py` implements and documents:
block mappings, block sequences and scalars. Flow style such as `[a, b]` is
rejected with exit 5 rather than half-read, because a policy file that is
partially parsed enforces a policy nobody agreed to.

## Exit codes and the gate

| Code | Meaning |
| --- | --- |
| 0 | PASS, no findings |
| 1 | violations found |
| 3 | NOT APPLICABLE, no configuration file |
| 4 | empty configuration file |
| 5 | malformed configuration, or an unknown marker or script name |
| 6 | internal error |

`scripts/policy_scan.sh` writes `.eng/artifacts/policy_scan.log` with a `RESULT:`
line and a trailing `EXIT_CODE=`, which is the contract `gate_check.sh` reads.

`G6_Policy` is NOT APPLICABLE when `.eng/policy.yaml` does not exist. A
repository that has not adopted a content policy is not failing one. `G6_Policy`
is part of `gate_check.sh all`, and a NOT APPLICABLE result does not drag the
overall verdict down.

## Relationship to the other gates

`G3_Security` reads `secret_scan.log` and `dep_audit.log`. `G6_Policy` reads
`policy_scan.log`. All three follow the same rule: the gate reports what the log
says, and the log records what the command returned. No gate reads `state.json`
to decide a PASS.

## This repository does not adopt the policy

`eng-orchestrator` has no `.eng/policy.yaml`, so `G6_Policy` reports NOT
APPLICABLE here. That is intentional. This repository uses `#` comments,
pictographs in its test output and documentation, Persian trigger phrases in
`SKILL.md`, and the organisation name in GitHub URLs. Applying the browser
platform example policy to this tree produces:

```
python3 scripts/policy_scan.py --config examples/browser-platform.policy.yaml --root . --max-findings 0
```

```
files scanned: 198
comments: 4 finding(s)
emoji: 98 finding(s)
language: 256 finding(s)
branding: 16 finding(s)
total findings: 374
```

The four comment findings are the intentional fixtures under
`tests/fixtures/policy/dirty/`. The rest are this repository being itself. None
of it is a defect here, which is the point: the scanner is a tool a project
adopts, not a rule the tool imposes.

