"""Profile engine: versioned environment descriptions with a migration path.

A profile is the unit a user configures and the unit that travels. Because it
travels, it is untrusted input the moment it arrives. Everything here is written
on that assumption: an imported profile is parsed, schema-checked, range-checked,
migrated if it is old, and only then offered for activation. Nothing is applied
as a side effect of being read.

Versioning is explicit. A profile states the version it was written against, and
an unknown or unhandled version is refused rather than interpreted hopefully. A
file that half-parses produces an environment nobody chose, which is the exact
outcome this module exists to prevent.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Optional

from .errors import ProfileError, ProfileImportError, ProfileSchemaError, ProfileVersionError
from .geo import RANDOMIZATION_MODES, RANDOMIZATION_STABLE, validate_coordinate, validate_radius
from .locale_engine import normalise_language_tag
from .timezone_engine import is_valid_identifier

CURRENT_VERSION = 3

IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
FORBIDDEN_IDENTIFIERS = {"", ".", "..", "default", "current", "active", "index"}

GEOLOCATION_MODES = ("virtual", "physical", "automatic", "hybrid", "disabled")
WEBRTC_POLICIES = ("default", "privacy_enhanced", "disable_local_candidates", "custom")
DNS_MODES = ("system", "custom", "doh", "dot")
CONSENT_MODES = ("prompt", "allow", "deny")

REQUIRED_FIELDS = ("identifier", "name")
KNOWN_FIELDS = {
    "profile_version",
    "identifier",
    "name",
    "country",
    "region",
    "city",
    "latitude",
    "longitude",
    "radius_m",
    "altitude_m",
    "timezone",
    "timezone_mode",
    "locale",
    "locale_mode",
    "languages",
    "geolocation_mode",
    "randomization",
    "randomization_seed",
    "dns_mode",
    "dns_resolver",
    "dns_fallback",
    "webrtc_policy",
    "consent_mode",
    "notes",
    "checksum",
}

STRING_FIELDS = (
    "identifier",
    "name",
    "country",
    "region",
    "city",
    "timezone",
    "locale",
    "geolocation_mode",
    "randomization",
    "dns_mode",
    "dns_resolver",
    "dns_fallback",
    "webrtc_policy",
    "consent_mode",
    "notes",
    "timezone_mode",
    "locale_mode",
)

NUMERIC_FIELDS = ("latitude", "longitude", "radius_m", "altitude_m", "profile_version", "randomization_seed")


def validate_identifier(identifier: str) -> str:
    if not isinstance(identifier, str) or not IDENTIFIER_PATTERN.match(identifier.strip().lower()):
        raise ProfileSchemaError(
            "profile identifier must be lowercase alphanumeric with dots, dashes or underscores",
            f"received {identifier!r}",
        )

    candidate = identifier.strip().lower()

    if candidate in FORBIDDEN_IDENTIFIERS:
        raise ProfileSchemaError(
            f"profile identifier {candidate!r} is reserved",
            "reserved names would collide with generated files and index entries",
        )

    return candidate


def canonical_json(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_checksum(payload: dict) -> str:
    """Checksum over the profile body, excluding the checksum itself.

    This detects corruption and accidental edits. It is not a signature and does
    not authenticate the author, which is why an imported profile is validated on
    its values rather than trusted because its checksum matches.
    """
    body = {key: value for key, value in payload.items() if key != "checksum"}

    return "sha256:" + hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()


def detect_version(payload: dict) -> int:
    if not isinstance(payload, dict):
        raise ProfileImportError("a profile must be a mapping", f"received {type(payload).__name__}")

    raw = payload.get("profile_version", 1)

    if isinstance(raw, bool) or not isinstance(raw, int):
        raise ProfileVersionError("profile_version must be an integer", f"received {raw!r}")

    if raw < 1:
        raise ProfileVersionError("profile_version must be at least 1", f"received {raw}")

    if raw > CURRENT_VERSION:
        raise ProfileVersionError(
            f"profile version {raw} is newer than this build supports ({CURRENT_VERSION})",
            "a newer profile may use fields this build would silently ignore",
        )

    return raw


def migrate(payload: dict) -> tuple:
    """Bring a profile up to the current version, recording each step.

    Returns the migrated payload and the list of migrations applied, so an
    import can report what changed rather than mutating in silence.
    """
    version = detect_version(payload)
    working = dict(payload)
    applied = []

    if version == 1:
        if "geolocation_mode" not in working:
            working["geolocation_mode"] = "virtual" if working.get("latitude") is not None else "automatic"
            applied.append("v1 to v2: derived geolocation_mode")
        if "randomization" not in working:
            working["randomization"] = RANDOMIZATION_STABLE
            applied.append("v1 to v2: defaulted randomization to stable")
        working["profile_version"] = 2
        version = 2

    if version == 2:
        if "dns_mode" not in working:
            working["dns_mode"] = "system"
            applied.append("v2 to v3: defaulted dns_mode to system")
        if "dns_fallback" not in working:
            working["dns_fallback"] = "refuse"
            applied.append("v2 to v3: defaulted dns_fallback to refuse")
        working["profile_version"] = 3
        version = 3

    return working, applied


def coerce_scalar(key: str, value):
    if value is None:
        return None

    if key in NUMERIC_FIELDS:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ProfileSchemaError(f"field {key!r} must be a number", f"received {value!r}")
        return value

    if key in STRING_FIELDS:
        if not isinstance(value, str):
            raise ProfileSchemaError(f"field {key!r} must be a string", f"received {value!r}")
        return value.strip()

    if key == "languages":
        if not isinstance(value, list):
            raise ProfileSchemaError("field 'languages' must be a list", f"received {type(value).__name__}")
        return [normalise_language_tag(item) for item in value]

    return value


def validate_payload(payload: dict, strict: bool = True) -> list:
    """Validate a migrated profile body and return the collected problems.

    Unknown fields are an error rather than a warning when strict. A profile
    written for a different schema is a profile whose author expected something
    this build does not do, and ignoring the difference applies an environment
    neither party agreed to.
    """
    problems = []

    if not isinstance(payload, dict):
        raise ProfileSchemaError("a profile must be a mapping", f"received {type(payload).__name__}")

    for field_name in REQUIRED_FIELDS:
        if not payload.get(field_name):
            problems.append(f"missing required field {field_name!r}")

    if strict:
        for field_name in sorted(set(payload) - KNOWN_FIELDS):
            problems.append(f"unknown field {field_name!r}")

    for field_name, value in payload.items():
        if field_name not in KNOWN_FIELDS or value is None:
            continue
        try:
            payload[field_name] = coerce_scalar(field_name, value)
        except ProfileSchemaError as error:
            problems.append(error.message)

    if "identifier" in payload and payload["identifier"]:
        try:
            payload["identifier"] = validate_identifier(payload["identifier"])
        except ProfileSchemaError as error:
            problems.append(error.message)

    if payload.get("latitude") is not None or payload.get("longitude") is not None:
        try:
            validate_coordinate(payload.get("latitude"), payload.get("longitude"))
        except Exception as error:
            problems.append(f"coordinates rejected: {getattr(error, 'message', error)}")

    if payload.get("radius_m") is not None:
        try:
            validate_radius(payload["radius_m"])
        except Exception as error:
            problems.append(f"radius rejected: {getattr(error, 'message', error)}")

    if payload.get("timezone") and not is_valid_identifier(payload["timezone"]):
        problems.append(f"timezone {payload['timezone']!r} is not in the local tz database")

    if payload.get("locale"):
        try:
            normalise_language_tag(payload["locale"])
        except Exception as error:
            problems.append(f"locale rejected: {getattr(error, 'message', error)}")

    mode = payload.get("geolocation_mode")

    if mode and mode not in GEOLOCATION_MODES:
        problems.append(f"geolocation_mode {mode!r} is not one of {GEOLOCATION_MODES}")

    randomization = payload.get("randomization")

    if randomization and randomization not in RANDOMIZATION_MODES:
        problems.append(f"randomization {randomization!r} is not one of {RANDOMIZATION_MODES}")

    dns_mode = payload.get("dns_mode")

    if dns_mode and dns_mode not in DNS_MODES:
        problems.append(f"dns_mode {dns_mode!r} is not one of {DNS_MODES}")

    webrtc = payload.get("webrtc_policy")

    if webrtc and webrtc not in WEBRTC_POLICIES:
        problems.append(f"webrtc_policy {webrtc!r} is not one of {WEBRTC_POLICIES}")

    consent = payload.get("consent_mode")

    if consent and consent not in CONSENT_MODES:
        problems.append(f"consent_mode {consent!r} is not one of {CONSENT_MODES}")

    if mode in ("virtual", "hybrid") and payload.get("latitude") is None:
        problems.append(f"geolocation_mode {mode!r} requires a latitude")

    if payload.get("radius_m", 0) and mode not in ("virtual", "hybrid"):
        problems.append(f"radius_m is set but geolocation_mode is {mode!r}, which does not sample an area")

    if dns_mode in ("custom", "doh", "dot") and not payload.get("dns_resolver"):
        problems.append(f"dns_mode {dns_mode!r} requires a dns_resolver")

    fallback = payload.get("dns_fallback")

    if fallback and fallback not in ("refuse", "system", "custom"):
        problems.append(f"dns_fallback {fallback!r} is not one of ('refuse', 'system', 'custom')")

    return problems


@dataclass
class GeoProfile:
    """A validated environment description."""

    identifier: str
    name: str
    profile_version: int = CURRENT_VERSION
    country: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    radius_m: float = 0.0
    altitude_m: Optional[float] = None
    timezone: Optional[str] = None
    timezone_mode: str = "profile"
    locale: Optional[str] = None
    locale_mode: str = "profile"
    languages: list = field(default_factory=list)
    geolocation_mode: str = "automatic"
    randomization: str = RANDOMIZATION_STABLE
    randomization_seed: Optional[int] = None
    dns_mode: str = "system"
    dns_resolver: Optional[str] = None
    dns_fallback: str = "refuse"
    webrtc_policy: str = "default"
    consent_mode: str = "prompt"
    notes: str = ""
    checksum: str = ""
    migrations: list = field(default_factory=list)

    def __post_init__(self):
        """Seal every profile with a checksum as soon as it exists.

        A profile that can be constructed without one would make verify_checksum
        meaningless for any profile built in code rather than imported, which is
        exactly the case the shipped defaults and the tests fall into.
        """
        if not self.checksum:
            self.checksum = compute_checksum(self.to_payload(include_checksum=False))

    @classmethod
    def from_payload(cls, payload: dict, strict: bool = True, migrate_old: bool = True) -> "GeoProfile":
        if migrate_old:
            working, applied = migrate(payload)
        else:
            working = dict(payload)
            applied = []

        problems = validate_payload(working, strict=strict)

        if problems:
            raise ProfileSchemaError(
                f"profile {working.get('identifier', '<unknown>')!r} failed validation",
                "; ".join(problems),
            )

        known = {key: value for key, value in working.items() if key in KNOWN_FIELDS}

        profile = cls(**{key: value for key, value in known.items() if key in cls.__dataclass_fields__})
        profile.profile_version = CURRENT_VERSION
        profile.migrations = applied
        profile.checksum = compute_checksum(profile.to_payload(include_checksum=False))

        return profile

    def to_payload(self, include_checksum: bool = True) -> dict:
        payload = {
            "profile_version": CURRENT_VERSION,
            "identifier": self.identifier,
            "name": self.name,
            "geolocation_mode": self.geolocation_mode,
            "randomization": self.randomization,
            "radius_m": self.radius_m,
            "timezone_mode": self.timezone_mode,
            "locale_mode": self.locale_mode,
            "dns_mode": self.dns_mode,
            "dns_fallback": self.dns_fallback,
            "webrtc_policy": self.webrtc_policy,
            "consent_mode": self.consent_mode,
        }

        optional = {
            "country": self.country,
            "region": self.region,
            "city": self.city,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "altitude_m": self.altitude_m,
            "timezone": self.timezone,
            "locale": self.locale,
            "dns_resolver": self.dns_resolver,
            "randomization_seed": self.randomization_seed,
            "notes": self.notes,
        }

        for key, value in optional.items():
            if value not in (None, ""):
                payload[key] = value

        if self.languages:
            payload["languages"] = list(self.languages)

        if include_checksum:
            payload["checksum"] = self.checksum

        return payload

    def as_dict(self) -> dict:
        result = self.to_payload(include_checksum=True)
        result["migrations"] = list(self.migrations)

        return result

    def verify_checksum(self) -> bool:
        if not self.checksum:
            return False

        return self.checksum == compute_checksum(self.to_payload(include_checksum=False))


class ProfileStore:
    """An in-memory profile collection with import, export and integrity checks."""

    def __init__(self):
        self._profiles: dict = {}

    def __len__(self) -> int:
        return len(self._profiles)

    def identifiers(self) -> list:
        return sorted(self._profiles)

    def get(self, identifier: str) -> Optional[GeoProfile]:
        return self._profiles.get(identifier)

    def add(self, profile: GeoProfile) -> GeoProfile:
        self._profiles[profile.identifier] = profile

        return profile

    def remove(self, identifier: str) -> bool:
        return self._profiles.pop(identifier, None) is not None

    def export(self, identifier: str) -> dict:
        profile = self._profiles.get(identifier)

        if profile is None:
            raise ProfileError(f"no profile named {identifier!r}", "nothing to export")

        return profile.to_payload(include_checksum=True)

    def import_payload(self, payload: dict, strict: bool = True, require_checksum: bool = False) -> GeoProfile:
        """Validate an untrusted payload and add it only if it survives.

        The checksum is optional on input and never sufficient on its own. A
        payload whose checksum matches but whose values are out of range is still
        rejected, because the checksum says the file is intact, not that it is
        safe or sensible.
        """
        if not isinstance(payload, dict):
            raise ProfileImportError("an imported profile must be a mapping", f"received {type(payload).__name__}")

        supplied = payload.get("checksum")

        if require_checksum and not supplied:
            raise ProfileImportError(
                "the imported profile carries no checksum",
                "this import required integrity metadata and did not find it",
            )

        working = {key: value for key, value in payload.items() if key != "checksum"}

        if supplied:
            expected = compute_checksum(dict(working))
            if expected != supplied:
                raise ProfileImportError(
                    "the imported profile failed its checksum",
                    f"expected {expected}, found {supplied}",
                )

        profile = GeoProfile.from_payload(working, strict=strict)

        if len(self._profiles) >= 256:
            raise ProfileImportError("the profile limit of 256 has been reached", "remove a profile before importing another")

        return self.add(profile)
