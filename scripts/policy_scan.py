#!/usr/bin/env python3
"""policy_scan.py - enforce repository content policy from `.eng/policy.yaml`.

Four rules, each independently switchable from configuration:

    comments    forbidden comment markers, detected with a per-language lexer
    emoji       Unicode emoji and pictographs
    language    characters from non-permitted writing systems
    branding    prohibited organisation or product strings outside permitted paths

Why a lexer instead of grep. A content policy that bans `//` must not flag
`https://example.com`, `a // b` (floor division), a `/` regex delimiter, or the
same characters inside a string literal. Matching characters blindly produces
findings nobody can act on, and a scanner whose findings are ignored is worse
than no scanner. Each dialect therefore declares which markers it actually has,
and the lexer tokenises strings, templates, regular expressions and comments
before any marker is reported.

Usage:
    python3 scripts/policy_scan.py --check
    python3 scripts/policy_scan.py
    python3 scripts/policy_scan.py --rule comments
    python3 scripts/policy_scan.py --json
    python3 scripts/policy_scan.py --config .eng/policy.yaml --root .

Exit codes: 0 PASS, 1 violations found, 3 NOT APPLICABLE (no config),
4 empty config, 5 malformed config, 6 internal error.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from project_profile import ParseError, lookup, parse  # noqa: E402

DEFAULT_CONFIG = ".eng/policy.yaml"

EXIT_PASS = 0
EXIT_VIOLATIONS = 1
EXIT_NOT_APPLICABLE = 3
EXIT_EMPTY = 4
EXIT_MALFORMED = 5
EXIT_ERROR = 6


class ConfigError(Exception):
    """The policy file asks for something the scanner does not implement."""


class EmptyConfigError(ConfigError):
    """The policy file parsed to nothing at all."""


def glob_to_regex(pattern: str) -> "re.Pattern[str]":
    """Translate a path glob into an anchored regular expression.

    `**/` matches any number of leading path segments, `**` matches anything
    including separators, `*` matches within a single segment, `?` one character.
    """
    out = []
    i = 0
    n = len(pattern)

    while i < n:
        char = pattern[i]

        if pattern.startswith("**/", i):
            out.append("(?:[^/]+/)*")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif char == "*":
            out.append("[^/]*")
            i += 1
        elif char == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(char))
            i += 1

    return re.compile("^" + "".join(out) + "$")


class GlobSet:
    """A compiled list of path globs, matched against POSIX-relative paths."""

    def __init__(self, patterns):
        self.patterns = [str(p) for p in (patterns or [])]
        self.regexes = [glob_to_regex(p) for p in self.patterns]

    def matches(self, path: str) -> bool:
        return any(regex.match(path) for regex in self.regexes)

    def __bool__(self) -> bool:
        return bool(self.regexes)


DEFAULT_EXCLUDE = [
    "**/.git/**",
    "**/node_modules/**",
    "**/.eng/runs/**",
    "**/dist/**",
    "**/build/**",
    "**/target/**",
    "**/out/**",
    "**/__pycache__/**",
    "**/.venv/**",
    "**/.mypy_cache/**",
    "**/.pytest_cache/**",
]


class Dialect:
    """Comment syntax a language actually has, and which literals hide markers."""

    def __init__(
        self,
        name,
        line_marker=None,
        block_start=None,
        block_end=None,
        hash_marker=None,
        nested_block=False,
        templates=False,
        regex_literal=False,
    ):
        self.name = name
        self.line_marker = line_marker
        self.block_start = block_start
        self.block_end = block_end
        self.hash_marker = hash_marker
        self.nested_block = nested_block
        self.templates = templates
        self.regex_literal = regex_literal

    def markers(self):
        found = []

        if self.hash_marker:
            found.append("hash")
        if self.line_marker:
            found.append("slash_line")
        if self.block_start:
            found.append("slash_block")

        return found


SLASH_LINE = "//"
SLASH_START = "/*"
SLASH_END = "*/"

DIALECTS = {
    "javascript": Dialect("javascript", SLASH_LINE, SLASH_START, SLASH_END, templates=True, regex_literal=True),
    "typescript": Dialect("typescript", SLASH_LINE, SLASH_START, SLASH_END, templates=True, regex_literal=True),
    "jsx": Dialect("jsx", SLASH_LINE, SLASH_START, SLASH_END, templates=True, regex_literal=True),
    "tsx": Dialect("tsx", SLASH_LINE, SLASH_START, SLASH_END, templates=True, regex_literal=True),
    "mjs": Dialect("mjs", SLASH_LINE, SLASH_START, SLASH_END, templates=True, regex_literal=True),
    "cjs": Dialect("cjs", SLASH_LINE, SLASH_START, SLASH_END, templates=True, regex_literal=True),
    "jsonc": Dialect("jsonc", SLASH_LINE, SLASH_START, SLASH_END),
    "c": Dialect("c", SLASH_LINE, SLASH_START, SLASH_END),
    "cpp": Dialect("cpp", SLASH_LINE, SLASH_START, SLASH_END),
    "objc": Dialect("objc", SLASH_LINE, SLASH_START, SLASH_END),
    "java": Dialect("java", SLASH_LINE, SLASH_START, SLASH_END),
    "kotlin": Dialect("kotlin", SLASH_LINE, SLASH_START, SLASH_END),
    "csharp": Dialect("csharp", SLASH_LINE, SLASH_START, SLASH_END),
    "go": Dialect("go", SLASH_LINE, SLASH_START, SLASH_END),
    "swift": Dialect("swift", SLASH_LINE, SLASH_START, SLASH_END, nested_block=True),
    "rust": Dialect("rust", SLASH_LINE, SLASH_START, SLASH_END, nested_block=True),
    "scala": Dialect("scala", SLASH_LINE, SLASH_START, SLASH_END, nested_block=True),
    "dart": Dialect("dart", SLASH_LINE, SLASH_START, SLASH_END),
    "php": Dialect("php", SLASH_LINE, SLASH_START, SLASH_END, hash_marker="#"),
    "css": Dialect("css", None, SLASH_START, SLASH_END),
    "scss": Dialect("scss", SLASH_LINE, SLASH_START, SLASH_END),
    "sass": Dialect("sass", SLASH_LINE, SLASH_START, SLASH_END),
    "less": Dialect("less", SLASH_LINE, SLASH_START, SLASH_END),
    "sql": Dialect("sql", "--", SLASH_START, SLASH_END),
    "python": Dialect("python", hash_marker="#"),
    "ruby": Dialect("ruby", hash_marker="#"),
    "perl": Dialect("perl", hash_marker="#"),
    "shell": Dialect("shell", hash_marker="#"),
    "yaml": Dialect("yaml", hash_marker="#"),
    "toml": Dialect("toml", hash_marker="#"),
    "ini": Dialect("ini", hash_marker="#"),
    "r": Dialect("r", hash_marker="#"),
    "makefile": Dialect("makefile", hash_marker="#"),
    "dockerfile": Dialect("dockerfile", hash_marker="#"),
    "gradle": Dialect("gradle", SLASH_LINE, SLASH_START, SLASH_END),
}

EXTENSION_MAP = {
    ".js": "javascript",
    ".mjs": "mjs",
    ".cjs": "cjs",
    ".jsx": "jsx",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".mts": "typescript",
    ".cts": "typescript",
    ".jsonc": "jsonc",
    ".c": "c",
    ".h": "c",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".hh": "cpp",
    ".m": "objc",
    ".mm": "objc",
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".cs": "csharp",
    ".go": "go",
    ".swift": "swift",
    ".rs": "rust",
    ".scala": "scala",
    ".dart": "dart",
    ".php": "php",
    ".phtml": "php",
    ".css": "css",
    ".scss": "scss",
    ".sass": "sass",
    ".less": "less",
    ".sql": "sql",
    ".py": "python",
    ".pyi": "python",
    ".rb": "ruby",
    ".pl": "perl",
    ".pm": "perl",
    ".sh": "shell",
    ".bash": "shell",
    ".zsh": "shell",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".ini": "ini",
    ".cfg": "ini",
    ".r": "r",
    ".gradle": "gradle",
    ".kts": "kotlin",
}

BASENAME_MAP = {
    "makefile": "makefile",
    "gnumakefile": "makefile",
    "dockerfile": "dockerfile",
}

REGEX_KEYWORDS = {
    "return",
    "typeof",
    "instanceof",
    "in",
    "of",
    "new",
    "delete",
    "void",
    "throw",
    "case",
    "do",
    "else",
    "yield",
    "await",
}

REGEX_PRECEDING = set("([{,;:=!&|?+-*%~^<>")


def dialect_for(path: str):
    name = pathlib.PurePosixPath(path).name.lower()

    if name in BASENAME_MAP:
        return DIALECTS[BASENAME_MAP[name]]

    suffix = pathlib.PurePosixPath(path).suffix.lower()

    return DIALECTS.get(EXTENSION_MAP.get(suffix, ""))


class Finding:
    """One violation, with enough context to act on it."""

    def __init__(self, rule, path, line, column, marker, snippet):
        self.rule = rule
        self.path = path
        self.line = line
        self.column = column
        self.marker = marker
        self.snippet = snippet

    def as_dict(self):
        return {
            "rule": self.rule,
            "path": self.path,
            "line": self.line,
            "column": self.column,
            "marker": self.marker,
            "snippet": self.snippet,
        }

    def format(self):
        return f"{self.path}:{self.line}:{self.column} [{self.rule}] {self.marker} | {self.snippet}"


def snippet_for(text, start, end, limit=90):
    body = text[start:end].replace("\t", " ").strip()
    body = " ".join(body.split())

    if len(body) > limit:
        body = body[: limit - 3] + "..."

    return body or "(empty)"


def line_start(text, index):
    found = text.rfind("\n", 0, index)

    return 0 if found == -1 else found + 1


def scan_comments(text, dialect, forbidden):
    """Yield comment spans whose marker is in `forbidden`.

    The lexer tracks single, double and template strings, regular-expression
    literals and block-comment nesting so that marker characters inside code
    constructs are never reported as comments.
    """
    n = len(text)
    i = 0
    line = 1
    prev_char = ""
    prev_word = ""

    while i < n:
        char = text[i]

        if char == "\n":
            line += 1
            prev_char = ""
            prev_word = ""
            i += 1
            continue

        if char in " \t\r":
            i += 1
            continue

        if dialect.hash_marker and text.startswith(dialect.hash_marker, i) and "hash" in forbidden:
            end = text.find("\n", i)
            end = n if end == -1 else end
            yield Finding("comments", "", line, i - line_start(text, i) + 1, "hash", snippet_for(text, i, end))
            i = end
            prev_char = ""
            prev_word = ""
            continue

        if dialect.line_marker and text.startswith(dialect.line_marker, i) and "slash_line" in forbidden:
            end = text.find("\n", i)
            end = n if end == -1 else end
            yield Finding("comments", "", line, i - line_start(text, i) + 1, "slash_line", snippet_for(text, i, end))
            i = end
            prev_char = ""
            prev_word = ""
            continue

        if dialect.block_start and text.startswith(dialect.block_start, i):
            start = i
            start_line = line
            depth = 1
            j = i + len(dialect.block_start)

            while j < n and depth > 0:
                if dialect.nested_block and text.startswith(dialect.block_start, j):
                    depth += 1
                    j += len(dialect.block_start)
                    continue

                if text.startswith(dialect.block_end, j):
                    depth -= 1
                    j += len(dialect.block_end)
                    continue

                if text[j] == "\n":
                    line += 1

                j += 1

            if "slash_block" in forbidden:
                yield Finding(
                    "comments",
                    "",
                    start_line,
                    start - line_start(text, start) + 1,
                    "slash_block",
                    snippet_for(text, start, j),
                )

            i = j
            prev_char = ""
            prev_word = ""
            continue

        if char in "\"'":
            quote = char
            j = i + 1

            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue

                if text[j] == "\n":
                    break

                if text[j] == quote:
                    j += 1
                    break

                j += 1

            i = j
            prev_char = quote
            prev_word = ""
            continue

        if dialect.templates and char == "`":
            j = i + 1

            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue

                if text[j] == "\n":
                    line += 1

                if text[j] == "`":
                    j += 1
                    break

                j += 1

            i = j
            prev_char = "`"
            prev_word = ""
            continue

        if dialect.regex_literal and char == "/" and regex_allowed(prev_char, prev_word):
            j = i + 1
            in_class = False

            while j < n:
                current = text[j]

                if current == "\\":
                    j += 2
                    continue

                if current == "[":
                    in_class = True
                elif current == "]":
                    in_class = False
                elif current == "/" and not in_class:
                    j += 1
                    break
                elif current == "\n":
                    j = i
                    break

                j += 1

            i = j if j > i else i + 1
            prev_char = "/"
            prev_word = ""
            continue

        if char.isalnum() or char in "_$":
            start = i

            while i < n and (text[i].isalnum() or text[i] in "_$"):
                i += 1

            prev_word = text[start:i]
            prev_char = prev_word[-1]
            continue

        prev_char = char
        prev_word = ""
        i += 1


def regex_allowed(prev_char, prev_word):
    """Decide whether a `/` opens a regular expression rather than a division.

    Heuristic, not a parser: a `/` starts a regex when the previous significant
    character cannot end an expression. The limitation is documented in
    docs/security/policy-scan.md; the failure mode is a missed finding, never a
    false one, because a division mistaken for a regex still swallows no comment.
    """
    if prev_char == "":
        return True

    if prev_char in REGEX_PRECEDING:
        return True

    return prev_word in REGEX_KEYWORDS


def parse_marker_list(values, dialect):
    """Resolve configured marker names against what the dialect really has."""
    allowed = set(dialect.markers())
    resolved = []

    for value in values:
        name = str(value).strip().lower()

        if name in ("slash", "slash_line"):
            name = "slash_line"
        elif name in ("block", "slash_block"):
            name = "slash_block"

        if name not in {"hash", "slash_line", "slash_block"}:
            raise ConfigError(f"unknown comment marker `{value}`")

        if name in allowed:
            resolved.append(name)

    return sorted(set(resolved))


EMOJI_CORE = [
    (0x1F000, 0x1F0FF, "mahjong and playing card symbols"),
    (0x1F100, 0x1F1FF, "enclosed alphanumeric supplement and regional indicators"),
    (0x1F200, 0x1F2FF, "enclosed ideographic supplement"),
    (0x1F300, 0x1F5FF, "miscellaneous symbols and pictographs"),
    (0x1F600, 0x1F64F, "emoticons"),
    (0x1F650, 0x1F67F, "ornamental dingbats"),
    (0x1F680, 0x1F6FF, "transport and map symbols"),
    (0x1F700, 0x1F77F, "alchemical symbols"),
    (0x1F780, 0x1F7FF, "geometric shapes extended"),
    (0x1F800, 0x1F8FF, "supplemental arrows"),
    (0x1F900, 0x1F9FF, "supplemental symbols and pictographs"),
    (0x1FA00, 0x1FA6F, "chess symbols"),
    (0x1FA70, 0x1FAFF, "symbols and pictographs extended-A"),
    (0x2600, 0x26FF, "miscellaneous symbols"),
    (0x2700, 0x27BF, "dingbats"),
    (0x2B00, 0x2BFF, "miscellaneous symbols and arrows"),
    (0x2300, 0x23FF, "technical symbols with emoji presentation"),
    (0xFE0F, 0xFE0F, "emoji variation selector"),
    (0x2049, 0x2049, "exclamation question mark"),
    (0x203C, 0x203C, "double exclamation mark"),
    (0x2139, 0x2139, "information source"),
    (0x24C2, 0x24C2, "circled latin capital letter M"),
    (0x2934, 0x2935, "curved arrows"),
    (0x3030, 0x3030, "wavy dash"),
    (0x303D, 0x303D, "part alternation mark"),
    (0x3297, 0x3297, "circled ideograph congratulation"),
    (0x3299, 0x3299, "circled ideograph secret"),
]

EMOJI_EXTENDED = [
    (0x2190, 0x21FF, "arrows"),
    (0x25A0, 0x25FF, "geometric shapes"),
    (0x00A9, 0x00A9, "copyright sign"),
    (0x00AE, 0x00AE, "registered sign"),
    (0x2122, 0x2122, "trade mark sign"),
]


def emoji_label(codepoint, extended):
    for low, high, label in EMOJI_CORE:
        if low <= codepoint <= high:
            return label

    if extended:
        for low, high, label in EMOJI_EXTENDED:
            if low <= codepoint <= high:
                return label

    return None


SCRIPTS = {
    "arabic": [(0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF), (0xFB50, 0xFDFF), (0xFE70, 0xFEFF)],
    "hebrew": [(0x0590, 0x05FF), (0xFB1D, 0xFB4F)],
    "cyrillic": [(0x0400, 0x04FF), (0x0500, 0x052F), (0x2DE0, 0x2DFF)],
    "greek": [(0x0370, 0x03FF), (0x1F00, 0x1FFF)],
    "cjk": [(0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xF900, 0xFAFF), (0x20000, 0x2A6DF)],
    "hiragana": [(0x3040, 0x309F)],
    "katakana": [(0x30A0, 0x30FF), (0x31F0, 0x31FF), (0xFF66, 0xFF9D)],
    "hangul": [(0x1100, 0x11FF), (0x3130, 0x318F), (0xAC00, 0xD7AF)],
    "thai": [(0x0E00, 0x0E7F)],
    "devanagari": [(0x0900, 0x097F), (0xA8E0, 0xA8FF)],
    "armenian": [(0x0530, 0x058F), (0xFB00, 0xFB17)],
    "georgian": [(0x10A0, 0x10FF), (0x2D00, 0x2D2F)],
    "khmer": [(0x1780, 0x17FF)],
    "lao": [(0x0E80, 0x0EFF)],
    "myanmar": [(0x1000, 0x109F)],
    "tamil": [(0x0B80, 0x0BFF)],
    "telugu": [(0x0C00, 0x0C7F)],
    "bengali": [(0x0980, 0x09FF)],
    "gujarati": [(0x0A80, 0x0AFF)],
    "gurmukhi": [(0x0A00, 0x0A7F)],
    "kannada": [(0x0C80, 0x0CFF)],
    "malayalam": [(0x0D00, 0x0D7F)],
    "sinhala": [(0x0D80, 0x0DFF)],
    "ethiopic": [(0x1200, 0x137F)],
    "tibetan": [(0x0F00, 0x0FFF)],
    "mongolian": [(0x1800, 0x18AF)],
    "cherokee": [(0x13A0, 0x13FF)],
    "syriac": [(0x0700, 0x074F)],
    "thaana": [(0x0780, 0x07BF)],
}

ACCENTED_LATIN = [(0x00C0, 0x00D6), (0x00D8, 0x00F6), (0x00F8, 0x00FF), (0x0100, 0x017F), (0x0180, 0x024F)]


def script_for(codepoint, names):
    for name in names:
        for low, high in SCRIPTS.get(name, []):
            if low <= codepoint <= high:
                return name

    return None


def accented_latin(codepoint):
    return any(low <= codepoint <= high for low, high in ACCENTED_LATIN)


def load_config(path):
    if not path.exists():
        return None

    try:
        data = parse(path.read_text(encoding="utf-8"))
    except ParseError as error:
        raise ConfigError(str(error)) from error

    if not isinstance(data, dict) or not data:
        raise EmptyConfigError("policy file parsed to nothing")

    return data


def enabled(data, rule):
    value = lookup(data, f"{rule}.enabled")

    return True if value is None else bool(value)


def as_list(value):
    """Normalise a config value to a list of scalars.

    An absent key, an empty mapping and an empty sequence all mean "nothing
    configured". That distinction matters: an include list that accidentally
    contains one empty entry would silently scan zero files and report PASS.
    """
    if value is None:
        return []

    if isinstance(value, list):
        return [item for item in value if not isinstance(item, (dict, list))]

    if isinstance(value, dict):
        return []

    return [value]


def iter_files(root, include, exclude):
    """Yield POSIX-relative paths of readable text files in scope."""
    root = pathlib.Path(root)

    for current, dirs, files in os.walk(root):
        relative_dir = pathlib.Path(current).relative_to(root).as_posix()
        relative_dir = "" if relative_dir == "." else relative_dir

        dirs[:] = [d for d in dirs if d != ".git"]

        for name in sorted(files):
            if relative_dir:
                relative = f"{relative_dir}/{name}"
            else:
                relative = name

            if exclude.matches(relative):
                continue

            if include and not include.matches(relative):
                continue

            full = pathlib.Path(current) / name

            if full.is_symlink():
                continue

            yield relative, full


def read_text(full):
    try:
        raw = full.read_bytes()
    except OSError:
        return None

    if b"\x00" in raw[:8192]:
        return None

    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return raw.decode("latin-1")
        except UnicodeDecodeError:
            return None


def run_comments(data, root, files):
    configured = [str(v).strip().lower() for v in as_list(lookup(data, "comments.forbid_markers"))]

    if not configured:
        configured = ["slash_line", "slash_block"]

    languages = {str(v).strip().lower() for v in as_list(lookup(data, "comments.languages"))}
    findings = []

    for relative, full in files:
        dialect = dialect_for(relative)

        if dialect is None:
            continue

        if languages and dialect.name not in languages:
            continue

        try:
            forbidden = parse_marker_list(configured, dialect)
        except ConfigError as error:
            raise ConfigError(f"{relative}: {error}") from error

        if not forbidden:
            continue

        text = read_text(full)

        if text is None:
            continue

        for finding in scan_comments(text, dialect, forbidden):
            finding.path = relative
            findings.append(finding)

    return findings


def run_emoji(data, root, files):
    extended = bool(lookup(data, "emoji.extended"))
    findings = []

    for relative, full in files:
        text = read_text(full)

        if text is None:
            continue

        line = 1
        column = 1

        for char in text:
            label = emoji_label(ord(char), extended)

            if label:
                name = f"U+{ord(char):04X} {label}"
                findings.append(Finding("emoji", relative, line, column, name, repr(char)))

            if char == "\n":
                line += 1
                column = 1
            else:
                column += 1

    return findings


def run_language(data, root, files):
    names = [str(v).strip().lower() for v in as_list(lookup(data, "language.forbid_scripts"))]
    unknown = [name for name in names if name not in SCRIPTS]

    if unknown:
        raise ConfigError("unknown writing system(s): " + ", ".join(sorted(unknown)))

    if not names:
        names = sorted(SCRIPTS)

    check_accented = bool(lookup(data, "language.forbid_accented_latin"))
    findings = []

    for relative, full in files:
        text = read_text(full)

        if text is None:
            continue

        line = 1
        column = 1

        for char in text:
            codepoint = ord(char)
            script = script_for(codepoint, names)

            if script:
                findings.append(
                    Finding(
                        "language",
                        relative,
                        line,
                        column,
                        f"non-permitted writing system `{script}`",
                        repr(char),
                    )
                )
            elif check_accented and accented_latin(codepoint):
                findings.append(
                    Finding(
                        "language",
                        relative,
                        line,
                        column,
                        "accented latin character",
                        repr(char),
                    )
                )

            if char == "\n":
                line += 1
                column = 1
            else:
                column += 1

    return findings


def run_branding(data, root, files):
    prohibited = [str(v) for v in as_list(lookup(data, "branding.prohibited")) if str(v).strip()]

    if not prohibited:
        return []

    case_sensitive = bool(lookup(data, "branding.case_sensitive"))
    word_boundary = bool(lookup(data, "branding.word_boundary"))
    allow_paths = GlobSet(as_list(lookup(data, "branding.allow_paths")))
    compiled = []

    for term in prohibited:
        pattern = re.escape(term)

        if word_boundary:
            pattern = rf"(?<![\w-]){pattern}(?![\w-])"

        compiled.append((term, re.compile(pattern, 0 if case_sensitive else re.IGNORECASE)))

    findings = []

    for relative, full in files:
        if allow_paths.matches(relative):
            continue

        text = read_text(full)

        if text is None:
            continue

        for line_number, line_text in enumerate(text.splitlines(), 1):
            for term, regex in compiled:
                for match in regex.finditer(line_text):
                    findings.append(
                        Finding(
                            "branding",
                            relative,
                            line_number,
                            match.start() + 1,
                            f"prohibited string `{term}`",
                            snippet_for(line_text, 0, len(line_text)),
                        )
                    )

    return findings


RULES = {
    "comments": run_comments,
    "emoji": run_emoji,
    "language": run_language,
    "branding": run_branding,
}

MAX_REPORTED_PER_RULE = 200


def main() -> int:
    parser = argparse.ArgumentParser(description="Enforce repository content policy.")
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--root", default=".")
    parser.add_argument("--rule", default="all", choices=["all", *RULES])
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--max-findings", type=int, default=MAX_REPORTED_PER_RULE)
    args = parser.parse_args()

    path = pathlib.Path(args.config)

    try:
        data = load_config(path)
    except EmptyConfigError as error:
        print(f"ERROR: {args.config}: {error}", file=sys.stderr)
        return EXIT_EMPTY
    except ConfigError as error:
        print(f"ERROR: {args.config}: {error}", file=sys.stderr)
        return EXIT_MALFORMED

    if data is None:
        if not args.check:
            print(f"NOT APPLICABLE: no {args.config}")
            print("RESULT: NOT APPLICABLE")
        return EXIT_NOT_APPLICABLE

    if args.check:
        active = [name for name in RULES if enabled(data, name)]
        print(f"OK: {path} parsed, rules enabled: {', '.join(active) or 'none'}")
        return EXIT_PASS

    include = GlobSet(as_list(lookup(data, "scope.include")))
    configured_exclude = as_list(lookup(data, "scope.exclude"))
    exclude = GlobSet(configured_exclude or DEFAULT_EXCLUDE)

    try:
        collected = list(iter_files(args.root, include, exclude))
    except OSError as error:
        print(f"ERROR: cannot walk {args.root}: {error}", file=sys.stderr)
        return EXIT_ERROR

    wanted = list(RULES) if args.rule == "all" else [args.rule]

    results = {}
    errors = []

    for name in wanted:
        if not enabled(data, name):
            results[name] = {"skipped": "disabled in config"}
            continue

        try:
            findings = RULES[name](data, args.root, collected)
        except ConfigError as error:
            errors.append(f"{name}: {error}")
            continue

        results[name] = {"findings": findings}

    if errors:
        for message in errors:
            print(f"ERROR: {message}", file=sys.stderr)
        return EXIT_MALFORMED

    if args.json:
        payload = {
            "config": args.config,
            "root": args.root,
            "files_scanned": len(collected),
            "results": {
                name: ({"skipped": value["skipped"]} if "skipped" in value else {"count": len(value["findings"])})
                for name, value in results.items()
            },
            "findings": [
                finding.as_dict()
                for value in results.values()
                if "findings" in value
                for finding in value["findings"]
            ],
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return EXIT_PASS

    total = 0

    print("=== POLICY SCAN v1.0 ===")
    print(f"config: {args.config}")
    print(f"root: {args.root}")
    print(f"files scanned: {len(collected)}")

    for name, value in results.items():
        if "skipped" in value:
            print(f"{name}: SKIPPED ({value['skipped']})")
            continue

        findings = value["findings"]
        total += len(findings)
        print(f"{name}: {len(findings)} finding(s)")

        for finding in findings[: args.max_findings]:
            print(f"  {finding.format()}")

        if len(findings) > args.max_findings:
            print(f"  ... {len(findings) - args.max_findings} more suppressed, use --json for the full list")

    print(f"total findings: {total}")

    if total:
        print("RESULT: FAIL")
        return EXIT_VIOLATIONS

    print("RESULT: PASS")
    return EXIT_PASS


if __name__ == "__main__":
    raise SystemExit(main())
