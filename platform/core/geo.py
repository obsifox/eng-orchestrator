"""Geo engine: resolves the location the browser reports to web content.

The engine never reads the operating system directly. It asks a provider, and
every provider states its own source and confidence, so a caller can always tell
a measured position from a configured one. That distinction is the whole point:
a virtual location that silently degrades into a physical one is a privacy
failure, not a fallback.

Radius semantics. A profile may describe an area rather than a point. The engine
then produces one coordinate inside that area. The distribution is uniform over
the disc, not uniform in radius: sampling r uniformly would crowd points toward
the centre, because a ring of radius r has circumference proportional to r.
"""

from __future__ import annotations

import hashlib
import math
import random
from dataclasses import dataclass, replace
from datetime import datetime, timezone as dt_timezone
from typing import Optional

from .errors import GeoProviderError, InvalidCoordinateError, InvalidRadiusError

EARTH_RADIUS_M = 6371008.8
MAX_RADIUS_M = 2000000.0

SOURCE_PHYSICAL = "physical"
SOURCE_VIRTUAL = "virtual"
SOURCE_AUTOMATIC = "automatic"
SOURCE_HYBRID = "hybrid"
SOURCE_DISABLED = "disabled"

CONFIDENCE_MEASURED = "measured"
CONFIDENCE_CONFIGURED = "configured"
CONFIDENCE_DERIVED = "derived"
CONFIDENCE_NONE = "none"

RANDOMIZATION_NONE = "none"
RANDOMIZATION_STABLE = "stable"
RANDOMIZATION_SESSION = "session"
RANDOMIZATION_DYNAMIC = "dynamic"
RANDOMIZATION_SEEDED = "seeded"

RANDOMIZATION_MODES = (
    RANDOMIZATION_NONE,
    RANDOMIZATION_STABLE,
    RANDOMIZATION_SESSION,
    RANDOMIZATION_DYNAMIC,
    RANDOMIZATION_SEEDED,
)


def validate_coordinate(latitude, longitude) -> tuple:
    """Return the pair as floats, or raise for anything not on the globe."""
    for value, name, limit in ((latitude, "latitude", 90.0), (longitude, "longitude", 180.0)):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise InvalidCoordinateError(f"{name} must be a number", f"received {value!r}")
        if not math.isfinite(float(value)):
            raise InvalidCoordinateError(f"{name} must be finite", f"received {value!r}")
        if abs(float(value)) > limit:
            raise InvalidCoordinateError(
                f"{name} must be between -{limit} and {limit}",
                f"received {value}",
            )
    return float(latitude), float(longitude)


def validate_radius(radius_m) -> float:
    """Return the radius as a float, or raise for a value with no valid disc."""
    if isinstance(radius_m, bool) or not isinstance(radius_m, (int, float)):
        raise InvalidRadiusError("radius must be a number", f"received {radius_m!r}")
    value = float(radius_m)
    if not math.isfinite(value):
        raise InvalidRadiusError("radius must be finite", f"received {radius_m!r}")
    if value < 0:
        raise InvalidRadiusError("radius must not be negative", f"received {radius_m}")
    if value > MAX_RADIUS_M:
        raise InvalidRadiusError(
            f"radius must not exceed {MAX_RADIUS_M:.0f} metres",
            f"received {radius_m}",
        )
    return value


def haversine_m(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
    """Great-circle distance in metres between two coordinates."""
    phi_a = math.radians(lat_a)
    phi_b = math.radians(lat_b)
    delta_phi = math.radians(lat_b - lat_a)
    delta_lambda = math.radians(lon_b - lon_a)

    inner = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi_a) * math.cos(phi_b) * math.sin(delta_lambda / 2.0) ** 2
    )

    return 2.0 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(inner)))


def destination_point(latitude: float, longitude: float, distance_m: float, bearing_rad: float) -> tuple:
    """Point reached by travelling distance_m from the origin along a bearing.

    Uses the spherical direct geodesic. The error against a WGS84 ellipsoid is
    below a metre at the radii a geo profile uses, so an ellipsoidal solution
    would add a dependency without changing an outcome.
    """
    phi_a = math.radians(latitude)
    lambda_a = math.radians(longitude)
    angular = distance_m / EARTH_RADIUS_M

    sin_phi_b = math.sin(phi_a) * math.cos(angular) + math.cos(phi_a) * math.sin(angular) * math.cos(bearing_rad)
    phi_b = math.asin(max(-1.0, min(1.0, sin_phi_b)))

    y = math.sin(bearing_rad) * math.sin(angular) * math.cos(phi_a)
    x = math.cos(angular) - math.sin(phi_a) * sin_phi_b
    lambda_b = lambda_a + math.atan2(y, x)

    lat_result = math.degrees(phi_b)
    lon_result = (math.degrees(lambda_b) + 540.0) % 360.0 - 180.0

    return lat_result, lon_result


def derive_seed(*parts) -> int:
    """Deterministic integer seed from any set of string parts."""
    joined = "|".join(str(part) for part in parts)
    digest = hashlib.sha256(joined.encode("utf-8")).digest()

    return int.from_bytes(digest[:8], "big")


@dataclass(frozen=True)
class GeoArea:
    """A centre and a radius that together describe where the browser may be."""

    latitude: float
    longitude: float
    radius_m: float = 0.0
    altitude_m: Optional[float] = None

    def __post_init__(self):
        validate_coordinate(self.latitude, self.longitude)
        validate_radius(self.radius_m)
        if self.altitude_m is not None and not isinstance(self.altitude_m, (int, float)):
            raise InvalidCoordinateError("altitude must be a number or absent", f"received {self.altitude_m!r}")

    @property
    def is_point(self) -> bool:
        return self.radius_m == 0.0

    def as_dict(self) -> dict:
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "radius_m": self.radius_m,
            "altitude_m": self.altitude_m,
        }


@dataclass(frozen=True)
class GeoLocation:
    """One resolved position, with its provenance attached."""

    latitude: float
    longitude: float
    accuracy_m: float
    source: str
    confidence: str
    timestamp: str
    radius_m: float = 0.0
    altitude_m: Optional[float] = None
    heading_deg: Optional[float] = None
    speed_mps: Optional[float] = None
    seed: Optional[int] = None
    provider: str = ""
    detail: str = ""

    def as_dict(self) -> dict:
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "accuracy_m": self.accuracy_m,
            "altitude_m": self.altitude_m,
            "heading_deg": self.heading_deg,
            "speed_mps": self.speed_mps,
            "timestamp": self.timestamp,
            "source": self.source,
            "confidence": self.confidence,
            "radius_m": self.radius_m,
            "seed": self.seed,
            "provider": self.provider,
            "detail": self.detail,
        }


def now_iso() -> str:
    return datetime.now(dt_timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class GeoProvider:
    """Interface every provider implements.

    A provider must state its source and confidence. A provider that cannot
    produce a location raises rather than returning a default, so no engine above
    it can invent a position.
    """

    name = "provider"
    source = SOURCE_DISABLED
    confidence = CONFIDENCE_NONE

    def resolve(self, area: GeoArea, context: dict) -> GeoLocation:
        raise NotImplementedError


class DisabledProvider(GeoProvider):
    """Refuses to produce a location, by design rather than by failure."""

    name = "disabled"
    source = SOURCE_DISABLED
    confidence = CONFIDENCE_NONE

    def resolve(self, area: GeoArea, context: dict) -> GeoLocation:
        raise GeoProviderError(
            "geolocation is disabled for this environment",
            "the active profile sets geolocation_mode to disabled",
        )


class VirtualProvider(GeoProvider):
    """Produces a coordinate from the configuration, never from the device.

    The randomization mode decides how the coordinate inside the area is chosen:

    none      the centre itself
    stable    derived from the profile identity, identical across restarts
    session   derived from the session identity, identical within one session
    dynamic   derived from the current instant, different on every call
    seeded    derived from an explicit seed, reproducible on demand
    """

    name = "virtual"
    source = SOURCE_VIRTUAL
    confidence = CONFIDENCE_CONFIGURED

    def __init__(self, area: GeoArea, mode: str = RANDOMIZATION_STABLE, seed: Optional[int] = None):
        if mode not in RANDOMIZATION_MODES:
            raise GeoProviderError(f"unknown randomization mode {mode!r}", f"expected one of {RANDOMIZATION_MODES}")
        self.area = area
        self.mode = mode
        self.seed = seed

    def _seed_for(self, context: dict) -> Optional[int]:
        if self.mode == RANDOMIZATION_NONE:
            return None
        if self.mode == RANDOMIZATION_STABLE:
            return derive_seed("stable", context.get("profile_id", ""), self.area.latitude, self.area.longitude)
        if self.mode == RANDOMIZATION_SESSION:
            return derive_seed("session", context.get("session_id", ""), self.area.latitude, self.area.longitude)
        if self.mode == RANDOMIZATION_DYNAMIC:
            return random.SystemRandom().getrandbits(64)
        return self.seed if self.seed is not None else derive_seed("seeded", self.area.latitude, self.area.longitude)

    def resolve(self, area: GeoArea, context: dict) -> GeoLocation:
        if area.radius_m == 0.0:
            return GeoLocation(
                latitude=area.latitude,
                longitude=area.longitude,
                accuracy_m=10.0,
                altitude_m=area.altitude_m,
                source=self.source,
                confidence=self.confidence,
                timestamp=now_iso(),
                radius_m=0.0,
                seed=None,
                provider=self.name,
                detail="a fixed point, so no randomization was applied",
            )

        seed = self._seed_for(context)

        if seed is None:
            latitude = area.latitude
            longitude = area.longitude
        else:
            generator = random.Random(seed)
            radius = area.radius_m * math.sqrt(generator.random())
            bearing = generator.uniform(0.0, 2.0 * math.pi)
            latitude, longitude = destination_point(area.latitude, area.longitude, radius, bearing)

        accuracy = area.radius_m if area.radius_m > 0 else 10.0

        return GeoLocation(
            latitude=round(latitude, 7),
            longitude=round(longitude, 7),
            accuracy_m=accuracy,
            altitude_m=area.altitude_m,
            source=self.source,
            confidence=self.confidence,
            timestamp=now_iso(),
            radius_m=area.radius_m,
            seed=seed,
            provider=self.name,
            detail=f"randomization mode {self.mode}",
        )


class PhysicalProvider(GeoProvider):
    """A device-derived position supplied by the host through a documented port.

    The geo engine never calls an operating system API itself. The host passes a
    callable, and the callable is the only route to a measured position.
    """

    name = "physical"
    source = SOURCE_PHYSICAL
    confidence = CONFIDENCE_MEASURED

    def __init__(self, reader=None):
        self.reader = reader

    def resolve(self, area: GeoArea, context: dict) -> GeoLocation:
        if self.reader is None:
            raise GeoProviderError(
                "no physical location source is available",
                "the host did not provide a reader, and the engine has no direct device access",
            )

        reading = self.reader()

        if reading is None:
            raise GeoProviderError(
                "the physical location source returned nothing",
                "a measured position is unavailable at this moment",
            )

        latitude, longitude = validate_coordinate(reading.get("latitude"), reading.get("longitude"))

        return GeoLocation(
            latitude=latitude,
            longitude=longitude,
            accuracy_m=float(reading.get("accuracy_m", 25.0)),
            altitude_m=reading.get("altitude_m"),
            heading_deg=reading.get("heading_deg"),
            speed_mps=reading.get("speed_mps"),
            source=self.source,
            confidence=self.confidence,
            timestamp=reading.get("timestamp") or now_iso(),
            provider=self.name,
            detail="measured by the host",
        )


class AutomaticProvider(GeoProvider):
    """A position derived from network and configuration signals.

    Detection is a guess from evidence, so the result is labelled derived rather
    than measured, and the confidence is carried through to diagnostics instead
    of being rounded up to certainty.
    """

    name = "automatic"
    source = SOURCE_AUTOMATIC
    confidence = CONFIDENCE_DERIVED

    def __init__(self, detector):
        self.detector = detector

    def resolve(self, area: GeoArea, context: dict) -> GeoLocation:
        if self.detector is None:
            raise GeoProviderError(
                "no automatic detector is configured",
                "automatic mode needs a detector that reports a centre and a confidence",
            )

        detected = self.detector(context)

        if not detected:
            raise GeoProviderError(
                "automatic detection produced no location",
                "no signal was strong enough to propose a centre",
            )

        latitude, longitude = validate_coordinate(detected.get("latitude"), detected.get("longitude"))
        radius = validate_radius(detected.get("radius_m", 0.0))

        return GeoLocation(
            latitude=latitude,
            longitude=longitude,
            accuracy_m=radius if radius else 50000.0,
            source=self.source,
            confidence=detected.get("confidence", self.confidence),
            timestamp=now_iso(),
            radius_m=radius,
            provider=self.name,
            detail=detected.get("reason", "derived from available signals"),
        )


class HybridProvider(GeoProvider):
    """A detected environment constrained by explicit user choices.

    The detected centre is kept, but any field the user pinned overrides the
    corresponding detected field. Every override is recorded so the interface can
    show exactly which decisions were automatic and which were made by hand.
    """

    name = "hybrid"
    source = SOURCE_HYBRID
    confidence = CONFIDENCE_DERIVED

    def __init__(self, detector, pinned: dict):
        self.detector = detector
        self.pinned = {key: value for key, value in (pinned or {}).items() if value is not None}

    def resolve(self, area: GeoArea, context: dict) -> GeoLocation:
        detected_raw = self.detector(context) if self.detector else None

        if not detected_raw:
            raise GeoProviderError(
                "hybrid mode has no detected basis",
                "hybrid needs a detected environment to constrain; none was available",
            )

        latitude, longitude = validate_coordinate(detected_raw.get("latitude"), detected_raw.get("longitude"))
        radius = validate_radius(detected_raw.get("radius_m", 0.0))

        applied = []
        base = GeoArea(latitude, longitude, radius, detected_raw.get("altitude_m"))
        virtual = VirtualProvider(base, self.pinned.get("randomization", RANDOMIZATION_STABLE))
        location = virtual.resolve(base, context)

        if "latitude" in self.pinned or "longitude" in self.pinned:
            pinned_lat = self.pinned.get("latitude", base.latitude)
            pinned_lon = self.pinned.get("longitude", base.longitude)
            pinned_lat, pinned_lon = validate_coordinate(pinned_lat, pinned_lon)
            base = GeoArea(pinned_lat, pinned_lon, self.pinned.get("radius_m", base.radius_m), base.altitude_m)
            virtual = VirtualProvider(base, self.pinned.get("randomization", RANDOMIZATION_STABLE))
            location = virtual.resolve(base, context)
            applied.extend(["latitude", "longitude"])

        if "radius_m" in self.pinned and "radius_m" not in applied:
            base = GeoArea(base.latitude, base.longitude, self.pinned["radius_m"], base.altitude_m)
            virtual = VirtualProvider(base, self.pinned.get("randomization", RANDOMIZATION_STABLE))
            location = virtual.resolve(base, context)
            applied.append("radius_m")

        return replace(
            location,
            source=self.source,
            confidence=self.confidence,
            provider=self.name,
            detail=(
                "detected centre constrained by " + ", ".join(sorted(set(applied)))
                if applied
                else "detected centre with no manual constraint"
            ),
        )


class GeoEngine:
    """Chooses a provider from the profile and resolves one location.

    The engine refuses to substitute one provider for another. If a virtual
    profile cannot be served, the caller gets an error, not a physical position.
    """

    def __init__(self, provider: GeoProvider, area: GeoArea):
        self.provider = provider
        self.area = area

    @property
    def mode(self) -> str:
        return self.provider.name

    def resolve(self, context: Optional[dict] = None) -> GeoLocation:
        context = context or {}

        location = self.provider.resolve(self.area, context)

        validate_coordinate(location.latitude, location.longitude)

        if self.area.radius_m > 0 and self.provider.source == SOURCE_VIRTUAL:
            drift = haversine_m(self.area.latitude, self.area.longitude, location.latitude, location.longitude)
            if drift > self.area.radius_m + 1.0:
                raise GeoProviderError(
                    "resolved coordinate falls outside the permitted radius",
                    f"drift {drift:.1f} m exceeds radius {self.area.radius_m:.1f} m",
                )

        return location
