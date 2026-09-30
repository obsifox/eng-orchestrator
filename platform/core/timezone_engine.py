"""Timezone engine: what clock the browser reports to web content.

Scope, stated plainly. This engine controls browser-visible timezone surfaces.
It does not change the operating system clock, nor the timezone any other
application sees. A page can read JavaScript Date offsets and Intl formats, and
those are what a browser-scoped setting can influence. Nothing here virtualises
the kernel clock.

The engine resolves a timezone identifier, validates it against the local tz
database, and reports the offset and daylight-saving state as they are at a
given instant. It also answers a diagnostic question the interface needs: does
this timezone look consistent with the location the geo engine just resolved?
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone as dt_timezone
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

from .errors import UnknownTimezoneError

MODE_AUTOMATIC = "automatic"
MODE_MANUAL = "manual"
MODE_PROFILE = "profile"
MODE_SYSTEM = "system"

MODES = (MODE_AUTOMATIC, MODE_MANUAL, MODE_PROFILE, MODE_SYSTEM)


_CASE_INDEX = None


def _case_index() -> dict:
    """A lowercase to canonical map over the local tz database, built once.

    IANA identifiers are case sensitive in principle. In practice a user types
    `europe/berlin`, and the tz database contains no two identifiers that differ
    only by case, so resolving the difference is unambiguous. Without this, the
    only identifier accepted in any case would be UTC.
    """
    global _CASE_INDEX

    if _CASE_INDEX is None:
        _CASE_INDEX = {name.lower(): name for name in available_timezones()}

    return _CASE_INDEX


def available_identifiers() -> list:
    return sorted(available_timezones())


def resolve_identifier(identifier: str):
    """Return the canonical identifier, or None if the database has no match."""
    if not isinstance(identifier, str) or not identifier.strip():
        return None

    candidate = identifier.strip().lstrip(":")

    if not candidate:
        return None

    if candidate.upper() in ("UTC", "GMT"):
        canonical = candidate.upper()

        if is_known(canonical):
            return canonical

    if is_known(candidate):
        return candidate

    return _case_index().get(candidate.lower())


def is_known(identifier: str) -> bool:
    try:
        ZoneInfo(identifier)
        return True
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        return False


def is_valid_identifier(identifier: str) -> bool:
    return resolve_identifier(identifier) is not None


def normalise(identifier: str) -> str:
    """Return a canonical identifier, or raise with the reason."""
    if not isinstance(identifier, str) or not identifier.strip():
        raise UnknownTimezoneError("timezone must be a non-empty string", f"received {identifier!r}")

    resolved = resolve_identifier(identifier)

    if resolved is None:
        raise UnknownTimezoneError(
            f"unknown timezone identifier {identifier.strip()!r}",
            "the local tz database does not contain this identifier",
        )

    return resolved


def offset_minutes(identifier: str, moment: Optional[datetime] = None) -> int:
    """UTC offset in minutes at the given instant."""
    zone = ZoneInfo(normalise(identifier))
    reference = moment or datetime.now(dt_timezone.utc)

    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=dt_timezone.utc)

    delta = reference.astimezone(zone).utcoffset() or dt_timezone.utc.utcoffset(reference)

    return int(delta.total_seconds() // 60)


def observes_daylight_saving(identifier: str, moment: Optional[datetime] = None) -> bool:
    """Whether the zone is in daylight saving at the given instant."""
    zone = ZoneInfo(normalise(identifier))
    reference = moment or datetime.now(dt_timezone.utc)

    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=dt_timezone.utc)

    daylight = reference.astimezone(zone).dst()

    return bool(daylight and daylight.total_seconds() != 0)


def format_offset(minutes: int) -> str:
    sign = "+" if minutes >= 0 else "-"
    absolute = abs(minutes)

    return f"{sign}{absolute // 60:02d}:{absolute % 60:02d}"


@dataclass(frozen=True)
class TimezoneResolution:
    """The resolved clock, plus how it was decided."""

    identifier: str
    mode: str
    offset_minutes: int
    offset_display: str
    daylight_saving: bool
    abbreviation: str
    source: str
    confidence: str
    detail: str = ""

    def as_dict(self) -> dict:
        return {
            "identifier": self.identifier,
            "mode": self.mode,
            "offset_minutes": self.offset_minutes,
            "offset_display": self.offset_display,
            "daylight_saving": self.daylight_saving,
            "abbreviation": self.abbreviation,
            "source": self.source,
            "confidence": self.confidence,
            "detail": self.detail,
        }


class TimezoneEngine:
    """Resolves the browser-scoped timezone from a profile and a host clock."""

    def __init__(self, system_identifier: str = "UTC", reporter=None):
        self.system_identifier = normalise(system_identifier)
        self.reporter = reporter

    def resolve(self, configured: Optional[str], mode: str, moment: Optional[datetime] = None) -> TimezoneResolution:
        if mode not in MODES:
            raise UnknownTimezoneError(f"unknown timezone mode {mode!r}", f"expected one of {MODES}")

        if mode == MODE_SYSTEM:
            identifier = self.system_identifier
            source = "host"
            confidence = "measured"
            detail = "inherited from the host, not virtualised"
        elif configured:
            identifier = normalise(configured)
            source = "manual" if mode == MODE_MANUAL else "profile"
            confidence = "configured"
            detail = "configured explicitly for this environment"
        else:
            identifier = self.system_identifier
            source = "host"
            confidence = "derived"
            detail = "no timezone configured, so the host value stands"

        zone = ZoneInfo(identifier)
        reference = moment or datetime.now(dt_timezone.utc)

        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=dt_timezone.utc)

        localised = reference.astimezone(zone)
        minutes = offset_minutes(identifier, reference)
        daylight = observes_daylight_saving(identifier, reference)

        return TimezoneResolution(
            identifier=identifier,
            mode=mode,
            offset_minutes=minutes,
            offset_display=format_offset(minutes),
            daylight_saving=daylight,
            abbreviation=localised.tzname() or identifier,
            source=source,
            confidence=confidence,
            detail=detail,
        )


PLAUSIBLE_OFFSETS_BY_REGION = {
    "Europe": range(-60, 241, 15),
    "Africa": range(-60, 241, 15),
    "Asia": range(180, 601, 15),
    "America": range(-600, 1, 15),
    "Atlantic": range(-240, 121, 15),
    "Indian": range(120, 361, 15),
    "Australia": range(480, 661, 15),
    "Pacific": range(-720, 781, 15),
}


def plausibility(identifier: str, offset: int) -> tuple:
    """Whether an offset is at least geographically possible for its region.

    This is a coarse sanity check for diagnostics, not a correctness proof.
    Europe spans several offsets, so a plausible offset is not necessarily the
    right one. An implausible offset, however, is definitely a mismatch worth
    showing the user.
    """
    region = identifier.split("/")[0]

    if region in ("UTC", "GMT") or "/" not in identifier:
        return True, "no regional baseline applies"

    allowed = PLAUSIBLE_OFFSETS_BY_REGION.get(region)

    if allowed is None:
        return True, f"no baseline recorded for {region}"

    if offset in allowed:
        return True, f"{region} spans this offset"

    return False, f"{region} does not normally reach {format_offset(offset)}"
