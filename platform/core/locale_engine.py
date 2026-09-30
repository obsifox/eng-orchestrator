"""Locale engine: which language and formatting the browser presents.

Five surfaces are commonly conflated under the word locale. They are not the
same value, they are not read from the same place, and a page can observe more
than one of them:

  browser_locale     the UI language of the browser itself
  language_pref      navigator.languages, ordered by preference
  http_language      the Accept-Language request header
  js_locale          the default locale used by Intl and toLocaleString
  system_locale      what the host operating system reports

A profile may set each independently. This engine validates them, derives the
ones that were left unset, and reports all five separately so the interface can
show what a page would actually see rather than one invented summary value.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from .errors import InvalidLocaleError

LANGUAGE_PATTERN = re.compile(r"^[A-Za-z]{2,3}$")
SCRIPT_PATTERN = re.compile(r"^[A-Za-z]{4}$")
REGION_PATTERN = re.compile(r"^[A-Za-z]{2}$|^[0-9]{3}$")
VARIANT_PATTERN = re.compile(r"^[A-Za-z0-9]{5,8}$|^[0-9][A-Za-z0-9]{3}$")

DEFAULT_LANGUAGE = "en"
DEFAULT_REGION = "US"

ACCEPT_LANGUAGE_LIMIT = 10


def normalise_language_tag(tag: str) -> str:
    """Validate and canonicalise a BCP-47 style language tag.

    Casing follows the usual convention: language lowercase, script title case,
    region uppercase. The tag is returned unchanged in meaning, so `en-us`,
    `EN-US` and `en-US` all resolve to `en-US`.

    The primary subtag is restricted to two or three letters. BCP-47 also permits
    four to eight letters for registered collections, but validating those needs
    the IANA subtag registry, and accepting any long word would let `english
    language` through as a well formed tag. Two and three letters cover every
    language a user is likely to configure, and rejecting the rest is the safer
    failure.
    """
    if not isinstance(tag, str) or not tag.strip():
        raise InvalidLocaleError("language tag must be a non-empty string", f"received {tag!r}")

    stripped = tag.strip()

    if stripped.startswith("-") or stripped.endswith("-") or "--" in stripped:
        raise InvalidLocaleError(
            "language tag has an empty subtag",
            f"received {tag!r}",
        )

    raw = stripped.replace("_", "-")
    parts = [part for part in raw.split("-") if part]

    if not parts:
        raise InvalidLocaleError("language tag has no subtags", f"received {tag!r}")

    language = parts[0].lower()

    if not LANGUAGE_PATTERN.match(language):
        raise InvalidLocaleError(
            f"language subtag {language!r} is not well formed",
            "expected two to three letters",
        )

    result = [language]
    index = 1

    if index < len(parts) and SCRIPT_PATTERN.match(parts[index]):
        result.append(parts[index].title())
        index += 1

    if index < len(parts) and REGION_PATTERN.match(parts[index]):
        result.append(parts[index].upper())
        index += 1

    while index < len(parts):
        if not VARIANT_PATTERN.match(parts[index]):
            raise InvalidLocaleError(
                f"subtag {parts[index]!r} is not a valid variant",
                "expected five to eight alphanumerics, or a digit followed by three",
            )
        result.append(parts[index].lower())
        index += 1

    return "-".join(result)


def primary_language(tag: str) -> str:
    return normalise_language_tag(tag).split("-")[0]


def region_of(tag: str) -> Optional[str]:
    for part in normalise_language_tag(tag).split("-")[1:]:
        if REGION_PATTERN.match(part):
            return part.upper()

    return None


def build_accept_language(tags: list, quality_decay: float = 0.1) -> str:
    """Build an Accept-Language header value from an ordered preference list.

    The first entry gets no quality parameter, because q=1.0 is the default and
    emitting it invites the question of why it is missing elsewhere. Later
    entries decay by a fixed step and stop before zero, since a quality of zero
    is a refusal rather than a weak preference.
    """
    cleaned = []

    for tag in tags:
        canonical = normalise_language_tag(tag)
        if canonical not in cleaned:
            cleaned.append(canonical)

    cleaned = cleaned[:ACCEPT_LANGUAGE_LIMIT]

    if not cleaned:
        return f"{DEFAULT_LANGUAGE}-{DEFAULT_REGION}"

    rendered = [cleaned[0]]

    for position, tag in enumerate(cleaned[1:], start=1):
        quality = max(0.1, round(1.0 - quality_decay * position, 1))
        rendered.append(f"{tag};q={quality:g}")

    return ",".join(rendered)


def derive_locale(language: str, region: Optional[str] = None) -> str:
    """Build a locale tag from a language and an optional region."""
    canonical = normalise_language_tag(language)
    parts = canonical.split("-")

    has_region = any(REGION_PATTERN.match(part) for part in parts[1:])

    if has_region or not region:
        return canonical

    return f"{canonical}-{normalise_language_tag(f'{parts[0]}-{region}').split('-')[-1]}"


@dataclass
class LocaleResolution:
    """All five locale surfaces, resolved and kept apart."""

    browser_locale: str
    language_pref: list = field(default_factory=list)
    http_language: str = ""
    js_locale: str = ""
    system_locale: str = ""
    source: str = "profile"
    confidence: str = "configured"
    detail: str = ""

    def as_dict(self) -> dict:
        return {
            "browser_locale": self.browser_locale,
            "language_pref": list(self.language_pref),
            "http_language": self.http_language,
            "js_locale": self.js_locale,
            "system_locale": self.system_locale,
            "source": self.source,
            "confidence": self.confidence,
            "detail": self.detail,
        }


class LocaleEngine:
    """Resolves the locale surfaces from a profile and the host defaults."""

    def __init__(self, system_locale: str = "en-US"):
        self.system_locale = normalise_language_tag(system_locale)

    def resolve(self, configured_locale: Optional[str], languages: Optional[list], mode: str = "profile") -> LocaleResolution:
        if mode not in ("automatic", "manual", "profile", "system"):
            raise InvalidLocaleError(f"unknown locale mode {mode!r}", "expected automatic, manual, profile or system")

        preference = []

        for tag in languages or []:
            canonical = normalise_language_tag(tag)
            if canonical not in preference:
                preference.append(canonical)

        if mode == "system":
            resolved_locale = self.system_locale
            source = "host"
            confidence = "measured"
            detail = "inherited from the host, not virtualised"
        elif configured_locale:
            resolved_locale = normalise_language_tag(configured_locale)
            source = "manual" if mode == "manual" else "profile"
            confidence = "configured"
            detail = "configured explicitly for this environment"
        elif preference:
            resolved_locale = preference[0]
            source = "derived"
            confidence = "derived"
            detail = "derived from the first language preference"
        else:
            resolved_locale = self.system_locale
            source = "host"
            confidence = "derived"
            detail = "nothing configured, so the host value stands"

        if not preference:
            preference = [resolved_locale]

        if resolved_locale not in preference:
            preference = [resolved_locale] + preference

        return LocaleResolution(
            browser_locale=resolved_locale,
            language_pref=preference,
            http_language=build_accept_language(preference),
            js_locale=resolved_locale,
            system_locale=self.system_locale,
            source=source,
            confidence=confidence,
            detail=detail,
        )


def consistency(locale: LocaleResolution, timezone_identifier: str, country: Optional[str]) -> tuple:
    """Whether the locale, the timezone and the stated country agree.

    Agreement here proves nothing about privacy, and disagreement is not always
    a mistake: a user may legitimately run an English interface on a Tokyo clock.
    The check exists so the interface can surface the combination rather than
    leaving the user to notice it later.
    """
    notes = []

    locale_region = region_of(locale.browser_locale)
    primary = primary_language(locale.browser_locale)

    if locale_region and country and locale_region != country.upper():
        notes.append(f"locale region {locale_region} does not match country {country.upper()}")

    if not locale_region:
        notes.append(f"locale {locale.browser_locale} names no region, so no comparison is possible")

    if primary != DEFAULT_LANGUAGE and country and locale_region is None:
        notes.append("language differs from the default and no region is stated")

    if timezone_identifier and "/" in timezone_identifier and country:
        region = timezone_identifier.split("/")[0]
        if region in ("Asia", "Australia", "Pacific") and country.upper() in ("US", "CA", "MX", "BR"):
            notes.append(f"timezone {timezone_identifier} is far from locale region {country.upper()}")

    return (len(notes) == 0, notes)
