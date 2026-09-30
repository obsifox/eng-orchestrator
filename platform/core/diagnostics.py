"""Diagnostics: what the environment exposes, and where it disagrees with itself.

Two jobs live here.

The first is consistency reporting. Several independent surfaces describe where
a user is: the resolved location, the clock, the locale, the language header,
the resolver, and whatever the network looks like from outside. When they
disagree, the disagreement is worth showing. The report does not claim that
agreeing signals protect anything, because they do not: a coherent environment is
easier to reason about, not a guarantee of anonymity, and the fingerprint surface
is far wider than the handful of values a browser-scoped setting can reach.

The second is redaction. A diagnostic export is the artefact most likely to be
pasted into a public issue, so the default is the redacted form, and the fullest
form requires an explicit request. Credentials are never exported at any level.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone as dt_timezone
from typing import Optional

REDACTION_FULL = "full"
REDACTION_REDACTED = "redacted"
REDACTION_MINIMAL = "minimal"

REDACTION_LEVELS = (REDACTION_FULL, REDACTION_REDACTED, REDACTION_MINIMAL)
DEFAULT_REDACTION = REDACTION_REDACTED

SENSITIVE_KEY_PATTERN = re.compile(
    r"(token|secret|password|passwd|credential|api[_-]?key|authorization|cookie|session[_-]?key)",
    re.IGNORECASE,
)

IPV4_PATTERN = re.compile(r"\b(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})\b")

COORDINATE_PRECISION = {
    REDACTION_FULL: 5,
    REDACTION_REDACTED: 2,
    REDACTION_MINIMAL: 0,
}

SEVERITY_INFO = "info"
SEVERITY_NOTICE = "notice"
SEVERITY_WARNING = "warning"

CONSISTENCY_CAVEAT = (
    "This report compares signals the environment controls. Agreement between "
    "them is not fingerprint protection, and disagreement is not necessarily a "
    "mistake: a user may reasonably run an English interface on a Tokyo clock."
)


def redact_ipv4(text: str) -> str:
    """Replace the last two octets of every IPv4 address."""
    def replace(match):
        first, second = match.group(1), match.group(2)
        return f"{first}.{second}.x.x"

    return IPV4_PATTERN.sub(replace, str(text))


def redact_value(key: str, value, level: str):
    if level not in REDACTION_LEVELS:
        raise ValueError(f"unknown redaction level {level!r}")

    if isinstance(key, str) and SENSITIVE_KEY_PATTERN.search(key):
        return "[removed]"

    if isinstance(value, str):
        if level == REDACTION_MINIMAL:
            return "[removed]" if len(value) > 0 else value
        return redact_ipv4(value)

    if isinstance(value, dict):
        return {item_key: redact_value(item_key, item_value, level) for item_key, item_value in value.items()}

    if isinstance(value, list):
        return [redact_value(key, item, level) for item in value]

    return value


def redact_coordinate(value: Optional[float], level: str) -> Optional[float]:
    """Round or remove a coordinate according to the requested level."""
    if value is None:
        return None

    if level == REDACTION_MINIMAL:
        return None

    digits = COORDINATE_PRECISION.get(level, 2)

    if digits == 0:
        return None

    return round(float(value), digits)


def redact_snapshot(snapshot: dict, level: str = DEFAULT_REDACTION) -> dict:
    """Apply a redaction level to a whole environment snapshot."""
    if level not in REDACTION_LEVELS:
        raise ValueError(f"unknown redaction level {level!r}")

    trimmed = redact_value("", snapshot, level)

    for section in ("geo",):
        block = trimmed.get(section)

        if isinstance(block, dict):
            for coordinate in ("latitude", "longitude"):
                if coordinate in block:
                    block[coordinate] = redact_coordinate(block.get(coordinate), level)

    if level == REDACTION_MINIMAL:
        keep = ("state", "generated_at", "profile", "duration_ms")

        return {key: trimmed[key] for key in keep if key in trimmed}

    trimmed["redaction_level"] = level

    if level == REDACTION_REDACTED:
        trimmed["redaction_note"] = "coordinates rounded, IP addresses masked, credential-shaped fields removed"

    return trimmed


@dataclass
class ConsistencyFinding:
    """One disagreement between two signals that both describe the environment."""

    identifier: str
    severity: str
    summary: str
    detail: str = ""
    surfaces: list = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "identifier": self.identifier,
            "severity": self.severity,
            "summary": self.summary,
            "detail": self.detail,
            "surfaces": list(self.surfaces),
        }


REGION_EXPECTED_TIMEZONE = {
    "US": "America",
    "CA": "America",
    "MX": "America",
    "BR": "America",
    "AR": "America",
    "GB": "Europe",
    "DE": "Europe",
    "FR": "Europe",
    "NL": "Europe",
    "ES": "Europe",
    "IT": "Europe",
    "SE": "Europe",
    "PL": "Europe",
    "JP": "Asia",
    "CN": "Asia",
    "IN": "Asia",
    "IR": "Asia",
    "SG": "Asia",
    "KR": "Asia",
    "AU": "Australia",
    "NZ": "Pacific",
}

EXPECTED_LOCALE_PREFIX = {
    "US": "en",
    "GB": "en",
    "AU": "en",
    "DE": "de",
    "FR": "fr",
    "ES": "es",
    "IT": "it",
    "NL": "nl",
    "SE": "sv",
    "PL": "pl",
    "JP": "ja",
    "CN": "zh",
    "KR": "ko",
    "IR": "fa",
    "BR": "pt",
    "MX": "es",
    "RU": "ru",
}


def analyse(snapshot: dict) -> dict:
    """Compare the resolved surfaces and report every disagreement found."""
    findings = []
    geo = snapshot.get("geo") or {}
    timezone_block = snapshot.get("timezone") or {}
    locale_block = snapshot.get("locale") or {}
    dns_block = snapshot.get("dns") or {}
    detected = snapshot.get("detected") or {}
    profile_block = snapshot.get("profile")

    country = None

    if isinstance(profile_block, dict):
        country = profile_block.get("country")

    timezone_identifier = timezone_block.get("identifier")
    locale_identifier = locale_block.get("browser_locale")
    primary = (locale_identifier or "").split("-")[0]

    if not geo:
        findings.append(
            ConsistencyFinding(
                "geo.unresolved",
                SEVERITY_WARNING,
                "no location was resolved",
                "the geo stage did not produce a position, so nothing can be compared against it",
                ["geolocation"],
            )
        )

    if country and timezone_identifier and "/" in timezone_identifier:
        expected = REGION_EXPECTED_TIMEZONE.get(str(country).upper())
        actual = timezone_identifier.split("/")[0]

        if expected and expected != actual:
            findings.append(
                ConsistencyFinding(
                    "timezone.country_mismatch",
                    SEVERITY_NOTICE,
                    f"timezone {timezone_identifier} is not in {expected}, which country {country} would suggest",
                    "a page comparing the clock with an expected region will notice this",
                    ["timezone", "geolocation"],
                )
            )

    if country and primary:
        expected_language = EXPECTED_LOCALE_PREFIX.get(str(country).upper())

        if expected_language and expected_language != primary:
            findings.append(
                ConsistencyFinding(
                    "locale.country_mismatch",
                    SEVERITY_NOTICE,
                    f"locale {locale_identifier} does not use the language {country} usually implies ({expected_language})",
                    "this is a legitimate configuration, but it is visible to a page that reads both",
                    ["locale", "geolocation"],
                )
            )

    if locale_block and timezone_block:
        if primary and timezone_identifier:
            far_pairs = (
                (primary in ("ja", "ko", "zh")) and str(timezone_identifier).startswith("America"),
                (primary in ("en", "de", "fr", "nl", "sv", "pl")) and str(timezone_identifier).startswith(("Asia", "Australia")),
            )
            if any(far_pairs):
                findings.append(
                    ConsistencyFinding(
                        "locale.timezone_distance",
                        SEVERITY_NOTICE,
                        f"locale {locale_identifier} sits far from timezone {timezone_identifier}",
                        "not an error on its own, and worth seeing before the combination is relied upon",
                        ["locale", "timezone"],
                    )
                )

    if dns_block.get("encrypted") is False and dns_block.get("mode") in ("doh", "dot"):
        findings.append(
            ConsistencyFinding(
                "dns.mode_claims_encryption",
                SEVERITY_WARNING,
                "an encrypted DNS mode resolved to a plan that is not encrypted",
                "the plan and the mode disagree, which should not be reachable",
                ["dns"],
            )
        )

    if dns_block.get("fallback") not in (None, "refuse"):
        findings.append(
            ConsistencyFinding(
                "dns.plaintext_fallback",
                SEVERITY_WARNING,
                "a plaintext DNS fallback is permitted",
                "whenever the preferred transport fails, queries become observable to the network",
                ["dns"],
            )
        )

    if dns_block.get("certificate_validated") is False and dns_block.get("encrypted"):
        findings.append(
            ConsistencyFinding(
                "dns.certificate_not_validated",
                SEVERITY_WARNING,
                "an encrypted transport is configured without certificate validation",
                "the channel is encrypted but not authenticated, so it does not provide the assurance it implies",
                ["dns"],
            )
        )

    if detected:
        detected_country = detected.get("country")

        if detected_country and country and str(detected_country).upper() != str(country).upper():
            findings.append(
                ConsistencyFinding(
                    "network.geo_mismatch",
                    SEVERITY_NOTICE,
                    f"the network looks like {detected_country} while the profile says {country}",
                    "a page that geolocates the connection and the browser separately will see two different answers",
                    ["network", "geolocation"],
                )
            )

    severity_rank = {SEVERITY_INFO: 0, SEVERITY_NOTICE: 1, SEVERITY_WARNING: 2}
    findings.sort(key=lambda finding: severity_rank.get(finding.severity, 0), reverse=True)

    return {
        "consistent": not findings,
        "finding_count": len(findings),
        "findings": [finding.as_dict() for finding in findings],
        "caveat": CONSISTENCY_CAVEAT,
        "surfaces_examined": ["geolocation", "timezone", "locale", "language", "dns", "network"],
        "surfaces_not_examined": [
            "canvas",
            "webgl",
            "audio",
            "fonts",
            "screen metrics",
            "hardware concurrency",
            "user agent details",
        ],
        "not_examined_note": (
            "These surfaces contribute to how a page identifies a browser. This core does not "
            "control them and therefore cannot report on them."
        ),
    }


def build_report(snapshot: dict, level: str = DEFAULT_REDACTION, application: str = "platform", engine_version: str = "0.1.0") -> dict:
    """Assemble the exportable diagnostic report at the requested level."""
    if level not in REDACTION_LEVELS:
        raise ValueError(f"unknown redaction level {level!r}")

    anonymised = redact_snapshot(snapshot, level)
    analysis = analyse(snapshot)

    return {
        "application": application,
        "engine_version": engine_version,
        "generated_at": datetime.now(dt_timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "redaction_level": level,
        "environment": anonymised,
        "consistency": analysis,
        "environment_state": snapshot.get("state"),
        "failed_stage": snapshot.get("failed_stage"),
    }
