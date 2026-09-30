"""Platform core: browser-scoped environment resolution.

The core is dependency-free and imports nothing that reaches the network. It
resolves what the browser should present from what the user configured and what
the host can report, and it records which of the two each value came from.
"""

from .diagnostics import (
    DEFAULT_REDACTION,
    REDACTION_LEVELS,
    analyse,
    build_report,
    redact_snapshot,
)
from .dns_engine import DnsEngine, ResolverProfile
from .environment import (
    EnvironmentPipeline,
    SitePolicy,
    STATES,
    resolve_policy,
)
from .geo import (
    GeoArea,
    GeoEngine,
    GeoLocation,
    RANDOMIZATION_MODES,
    haversine_m,
)
from .locale_engine import LocaleEngine, build_accept_language
from .profiles import CURRENT_VERSION, GeoProfile, ProfileStore
from .timezone_engine import TimezoneEngine

__all__ = [
    "CURRENT_VERSION",
    "DEFAULT_REDACTION",
    "DnsEngine",
    "EnvironmentPipeline",
    "GeoArea",
    "GeoEngine",
    "GeoLocation",
    "GeoProfile",
    "LocaleEngine",
    "ProfileStore",
    "RANDOMIZATION_MODES",
    "REDACTION_LEVELS",
    "ResolverProfile",
    "STATES",
    "SitePolicy",
    "TimezoneEngine",
    "analyse",
    "build_accept_language",
    "build_report",
    "haversine_m",
    "redact_snapshot",
    "resolve_policy",
]

ENGINE_VERSION = "0.1.0"
