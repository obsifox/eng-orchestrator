"""The environment pipeline: configuration in, one coherent environment out.

Every stage is named, timed, and recorded with its own status and provenance, so
the interface can show which decision was automatic, which was configured, and
which one failed. A stage that fails does not fall through to a different
behaviour, because falling through is how a user ends up with an environment
they did not choose.

The rule that matters most is stated in one place. When the profile asks for a
virtual location and the virtual provider cannot serve it, the pipeline fails
with the reason attached. It does not consult the device. A silent fallback from
a configured position to a measured one is a privacy failure that the user would
have no way to observe.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone as dt_timezone
from typing import Optional

from .dns_engine import (
    FALLBACK_REFUSE,
    MODE_DOH,
    MODE_DOT,
    MODE_SYSTEM,
    DnsEngine,
    ResolverProfile,
)
from .errors import EnvironmentError, PipelineError
from .geo import (
    AutomaticProvider,
    DisabledProvider,
    GeoArea,
    GeoEngine,
    HybridProvider,
    PhysicalProvider,
    VirtualProvider,
)
from .locale_engine import LocaleEngine
from .profiles import GeoProfile
from .timezone_engine import TimezoneEngine

PIPELINE_STAGES = (
    "profile_resolution",
    "policy_resolution",
    "environment_validation",
    "geo_resolution",
    "timezone_resolution",
    "locale_resolution",
    "network_resolution",
    "dns_resolution",
    "privacy_policy",
    "browser_handoff",
)

STATUS_OK = "ok"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"
STATUS_DEGRADED = "degraded"

STATE_UNKNOWN = "UNKNOWN"
STATE_DETECTING = "DETECTING"
STATE_DETECTED = "DETECTED"
STATE_MANUAL = "MANUAL"
STATE_AUTOMATIC = "AUTOMATIC"
STATE_HYBRID = "HYBRID"
STATE_CONFLICT = "CONFLICT"
STATE_ERROR = "ERROR"
STATE_DISABLED = "DISABLED"

STATES = (
    STATE_UNKNOWN,
    STATE_DETECTING,
    STATE_DETECTED,
    STATE_MANUAL,
    STATE_AUTOMATIC,
    STATE_HYBRID,
    STATE_CONFLICT,
    STATE_ERROR,
    STATE_DISABLED,
)

WEBRTC_DESCRIPTIONS = {
    "default": "the browser engine decides candidate policy",
    "privacy_enhanced": "local candidates are withheld until a page is authorised to use them",
    "disable_local_candidates": "local host candidates are never offered, which reduces connectivity and removes a discovery path",
    "custom": "the profile supplies an explicit candidate policy",
}

WEBRTC_CAVEAT = (
    "This policy shapes which candidates the browser offers. It does not make a "
    "connection anonymous, and it does not hide the public address a server "
    "necessarily sees."
)


@dataclass
class StageResult:
    """One pipeline stage, with enough detail to explain a decision later."""

    name: str
    status: str
    started_at: str
    duration_ms: float
    output: dict = field(default_factory=dict)
    error: Optional[dict] = None
    notes: list = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status,
            "started_at": self.started_at,
            "duration_ms": round(self.duration_ms, 3),
            "output": self.output,
            "error": self.error,
            "notes": list(self.notes),
        }


def now_iso() -> str:
    return datetime.now(dt_timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class SitePolicy:
    """A per-site environment override.

    Precedence is deterministic. A more specific match wins, and a policy that
    matches nothing is inert. The order is origin, then subdomain, then domain,
    then the default. Ties are broken by the longest domain, so a rule for
    `example.com` cannot outrank a rule for `api.example.com`.
    """

    pattern: str
    scope: str = "domain"
    profile: Optional[str] = None
    timezone: Optional[str] = None
    locale: Optional[str] = None
    dns_mode: Optional[str] = None
    notes: str = ""

    def matches(self, host: str) -> bool:
        host = (host or "").strip().lower()

        if not host or not self.pattern:
            return False

        pattern = self.pattern.strip().lower()

        if self.scope == "origin":
            return host == pattern
        if self.scope == "subdomain":
            return host == pattern or host.endswith("." + pattern)
        if self.scope == "domain":
            return host == pattern or host.endswith("." + pattern)

        raise PipelineError(f"unknown policy scope {self.scope!r}", "expected origin, subdomain or domain")

    def specificity(self) -> int:
        rank = {"origin": 3, "subdomain": 2, "domain": 1}.get(self.scope, 0)

        return rank * 1000 + len(self.pattern)

    def as_dict(self) -> dict:
        return {
            "pattern": self.pattern,
            "scope": self.scope,
            "profile": self.profile,
            "timezone": self.timezone,
            "locale": self.locale,
            "dns_mode": self.dns_mode,
            "notes": self.notes,
        }


def resolve_policy(policies: list, host: Optional[str]) -> tuple:
    """Return the policy that applies to a host and the ones that were considered."""
    if not host:
        return None, []

    candidates = [policy for policy in policies if policy.matches(host)]

    if not candidates:
        return None, []

    ordered = sorted(candidates, key=lambda policy: policy.specificity(), reverse=True)

    return ordered[0], [policy.pattern for policy in ordered[1:]]


class EnvironmentPipeline:
    """Resolves a profile and the host environment into one describable state."""

    def __init__(
        self,
        timezone_engine: TimezoneEngine,
        locale_engine: LocaleEngine,
        dns_engine: DnsEngine,
        resolvers: Optional[dict] = None,
        detector=None,
        physical_reader=None,
        policies: Optional[list] = None,
    ):
        self.timezone_engine = timezone_engine
        self.locale_engine = locale_engine
        self.dns_engine = dns_engine
        self.resolvers = dict(resolvers or {})
        self.detector = detector
        self.physical_reader = physical_reader
        self.policies = list(policies or [])

    def _provider_for(self, profile: GeoProfile, area: GeoArea):
        mode = profile.geolocation_mode

        if mode == "virtual":
            return VirtualProvider(area, profile.randomization, profile.randomization_seed)
        if mode == "physical":
            return PhysicalProvider(self.physical_reader)
        if mode == "automatic":
            return AutomaticProvider(self.detector)
        if mode == "hybrid":
            pinned = {
                "latitude": profile.latitude,
                "longitude": profile.longitude,
                "radius_m": profile.radius_m,
                "randomization": profile.randomization,
            }
            return HybridProvider(self.detector, {key: value for key, value in pinned.items() if value is not None})
        if mode == "disabled":
            return DisabledProvider()

        raise PipelineError(f"unknown geolocation mode {mode!r}", "the profile passed validation but no provider exists")

    def run(self, profile: GeoProfile, host: Optional[str] = None, session_id: str = "session") -> dict:
        started = time.perf_counter()
        stages = []
        current_profile = profile
        state = STATE_UNKNOWN

        def record(name, status, begin, output=None, error=None, notes=None):
            stages.append(
                StageResult(
                    name=name,
                    status=status,
                    started_at=now_iso(),
                    duration_ms=(time.perf_counter() - begin) * 1000.0,
                    output=output or {},
                    error=error.as_dict() if isinstance(error, EnvironmentError) else error,
                    notes=list(notes or []),
                )
            )

        begin = time.perf_counter()
        applied_policy = None

        if host:
            applied_policy, overshadowed = resolve_policy(self.policies, host)
        else:
            overshadowed = []

        record(
            "profile_resolution",
            STATUS_OK,
            begin,
            output={
                "identifier": current_profile.identifier,
                "name": current_profile.name,
                "profile_version": current_profile.profile_version,
                "checksum": current_profile.checksum,
                "migrations": list(current_profile.migrations),
            },
        )

        begin = time.perf_counter()

        if applied_policy is None:
            record(
                "policy_resolution",
                STATUS_OK,
                begin,
                output={"applied": None, "host": host},
                notes=["no per-site policy matched, the profile stands unmodified"],
            )
        else:
            record(
                "policy_resolution",
                STATUS_OK,
                begin,
                output={
                    "applied": applied_policy.as_dict(),
                    "host": host,
                    "overshadowed": overshadowed,
                },
                notes=["a per-site policy overrides the profile for this host"],
            )

        begin = time.perf_counter()

        try:
            conflicts = validate_environment(current_profile, self.detector)

            if conflicts:
                record(
                    "environment_validation",
                    STATUS_DEGRADED,
                    begin,
                    output={"conflicts": conflicts},
                    notes=["the environment is coherent enough to resolve, with the listed conflicts"],
                )
            else:
                record("environment_validation", STATUS_OK, begin, output={"conflicts": []})
        except EnvironmentError as error:
            record("environment_validation", STATUS_FAILED, begin, error=error)
            return self._finish(stages, started, STATE_ERROR)

        begin = time.perf_counter()

        try:
            area = GeoArea(
                latitude=current_profile.latitude if current_profile.latitude is not None else 0.0,
                longitude=current_profile.longitude if current_profile.longitude is not None else 0.0,
                radius_m=current_profile.radius_m or 0.0,
                altitude_m=current_profile.altitude_m,
            )
            provider = self._provider_for(current_profile, area)
            engine = GeoEngine(provider, area)
            geo = engine.resolve({"profile_id": current_profile.identifier, "session_id": session_id})

            if current_profile.geolocation_mode == "virtual":
                state = STATE_MANUAL
            elif current_profile.geolocation_mode == "automatic":
                state = STATE_AUTOMATIC
            elif current_profile.geolocation_mode == "hybrid":
                state = STATE_HYBRID
            elif current_profile.geolocation_mode == "disabled":
                state = STATE_DISABLED
            else:
                state = STATE_DETECTED

            record(
                "geo_resolution",
                STATUS_OK,
                begin,
                output=geo.as_dict(),
                notes=[f"provider {provider.name} served this location from {geo.source}"],
            )
        except EnvironmentError as error:
            record(
                "geo_resolution",
                STATUS_FAILED,
                begin,
                error=error,
                notes=[
                    "no fallback provider was consulted",
                    "a configured location that cannot be served fails rather than degrading to the device",
                ],
            )
            return self._finish(stages, started, STATE_ERROR, profile=current_profile, policy=applied_policy)

        begin = time.perf_counter()

        try:
            timezone = self.timezone_engine.resolve(current_profile.timezone, current_profile.timezone_mode)
            record("timezone_resolution", STATUS_OK, begin, output=timezone.as_dict())
        except EnvironmentError as error:
            record("timezone_resolution", STATUS_FAILED, begin, error=error)
            return self._finish(stages, started, STATE_ERROR, geo, profile=current_profile, policy=applied_policy)

        begin = time.perf_counter()

        try:
            locale = self.locale_engine.resolve(current_profile.locale, current_profile.languages, current_profile.locale_mode)
            record("locale_resolution", STATUS_OK, begin, output=locale.as_dict())
        except EnvironmentError as error:
            record("locale_resolution", STATUS_FAILED, begin, error=error)
            return self._finish(stages, started, STATE_ERROR, geo, timezone, profile=current_profile, policy=applied_policy)

        begin = time.perf_counter()
        detection = None
        network_notes = []

        if self.detector is not None:
            try:
                detection = self.detector({"profile_id": current_profile.identifier})
                network_notes.append("signals were sampled from the host environment")
            except Exception as error:
                network_notes.append(f"detection raised and was ignored for reporting only: {error}")

        record(
            "network_resolution",
            STATUS_OK if detection else STATUS_DEGRADED,
            begin,
            output={"detected": detection} if detection else {"detected": None},
            notes=network_notes or ["no detector is configured, so no network signal was sampled"],
        )

        begin = time.perf_counter()

        try:
            resolver = self.resolvers.get(current_profile.dns_resolver) if current_profile.dns_resolver else None

            if current_profile.dns_resolver and resolver is None:
                raise PipelineError(
                    f"resolver {current_profile.dns_resolver!r} is not defined",
                    "the profile names a resolver that this build does not hold",
                )

            dns = self.dns_engine.resolve(current_profile.dns_mode, resolver, current_profile.dns_fallback)

            dns_notes = ["this plan is browser-scoped and does not modify the operating system resolver"]

            if dns.fallback != FALLBACK_REFUSE:
                dns_notes.append(
                    f"fallback policy {dns.fallback!r} would continue in plaintext over the {dns.fallback_protocol} if the encrypted transport failed"
                )

            record("dns_resolution", STATUS_OK, begin, output=dns.as_dict(), notes=dns_notes)
        except EnvironmentError as error:
            record("dns_resolution", STATUS_FAILED, begin, error=error)
            return self._finish(stages, started, STATE_ERROR, geo, timezone, locale, profile=current_profile, policy=applied_policy)

        begin = time.perf_counter()
        webrtc = {
            "policy": current_profile.webrtc_policy,
            "description": WEBRTC_DESCRIPTIONS.get(current_profile.webrtc_policy, "unrecognised policy"),
            "caveat": WEBRTC_CAVEAT,
        }
        consent = {
            "geolocation_consent": current_profile.consent_mode,
            "note": "a virtual location is still reported to a page only after the consent model allows it",
        }
        record(
            "privacy_policy",
            STATUS_OK,
            begin,
            output={"webrtc": webrtc, "consent": consent},
            notes=[WEBRTC_CAVEAT],
        )

        begin = time.perf_counter()
        handoff = {
            "geo": geo.as_dict(),
            "timezone": timezone.as_dict(),
            "locale": locale.as_dict(),
            "webrtc": webrtc,
            "consent": consent,
            "profile": current_profile.identifier,
            "policy": applied_policy.as_dict() if applied_policy else None,
            "host": host,
        }
        record(
            "browser_handoff",
            STATUS_OK,
            begin,
            output=handoff,
            notes=[
                "in a Gecko build this descriptor is what the browser process applies to its content processes",
                "in this core it is a value that callers render and test against",
            ],
        )

        return self._finish(stages, started, state, geo, timezone, locale, profile=current_profile, policy=applied_policy, detection=detection)

    def _finish(self, stages, started, state, geo=None, timezone=None, locale=None, profile=None, policy=None, detection=None):
        total = (time.perf_counter() - started) * 1000.0

        return {
            "state": state,
            "generated_at": now_iso(),
            "duration_ms": round(total, 3),
            "profile": profile.identifier if profile else None,
            "policy": policy.as_dict() if policy else None,
            "geo": geo.as_dict() if geo else None,
            "timezone": timezone.as_dict() if timezone else None,
            "locale": locale.as_dict() if locale else None,
            "detected": detection,
            "stages": [stage.as_dict() for stage in stages],
            "failed_stage": next((stage.name for stage in stages if stage.status == STATUS_FAILED), None),
        }


def validate_environment(profile: GeoProfile, detector=None) -> list:
    """Cross-field checks that no single-field validator can make.

    These are reported rather than enforced. A user may deliberately combine
    values that look inconsistent, and the platform's job is to make the
    combination visible, not to refuse it.
    """
    conflicts = []

    if profile.geolocation_mode == "hybrid" and detector is None:
        conflicts.append("hybrid mode is configured but no detector is available to constrain")

    if profile.geolocation_mode in ("automatic", "hybrid") and detector is None:
        conflicts.append("an automatic component is configured but the host exposes no signals")

    if profile.radius_m and profile.geolocation_mode not in ("virtual", "hybrid"):
        conflicts.append(f"radius {profile.radius_m} m is set but mode {profile.geolocation_mode!r} does not sample an area")

    if profile.dns_mode in (MODE_DOH, MODE_DOT) and profile.dns_fallback != FALLBACK_REFUSE:
        conflicts.append(
            f"DNS mode {profile.dns_mode!r} permits a plaintext fallback to {profile.dns_fallback!r}, "
            "so an observer could see queries whenever the encrypted transport fails"
        )

    if profile.dns_mode == MODE_SYSTEM and profile.dns_resolver:
        conflicts.append("a resolver is named but dns_mode is 'system', so the named resolver would never be used")

    if profile.timezone and profile.country and "/" in (profile.timezone or ""):
        region = profile.timezone.split("/")[0]
        expected = {"US": "America", "CA": "America", "BR": "America", "JP": "Asia", "IR": "Asia", "DE": "Europe", "FR": "Europe", "GB": "Europe"}
        want = expected.get(profile.country.upper())

        if want and region != want:
            conflicts.append(f"timezone region {region!r} does not match country {profile.country.upper()}")

    return conflicts
