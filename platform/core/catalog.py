"""Catalog: the sample data the application ships with.

Everything here is local. No catalogue lookup leaves the process, and no
location search queries a remote service, because a browser-scoped privacy tool
that phones a geocoding provider every time the user opens the location picker
has disclosed the one thing the user was configuring.

The city list is a small offline subset intended for demonstration and testing,
not a gazetteer. A production build would ship a public-domain dataset and record
it in the third-party resource manifest.
"""

from __future__ import annotations

from .dns_engine import ResolverProfile
from .environment import SitePolicy
from .profiles import GeoProfile

CITIES = [
    {"city": "Berlin", "region": "Berlin", "country": "DE", "latitude": 52.5200, "longitude": 13.4050, "timezone": "Europe/Berlin", "locale": "de-DE"},
    {"city": "Frankfurt am Main", "region": "Hesse", "country": "DE", "latitude": 50.1109, "longitude": 8.6821, "timezone": "Europe/Berlin", "locale": "de-DE"},
    {"city": "Amsterdam", "region": "North Holland", "country": "NL", "latitude": 52.3676, "longitude": 4.9041, "timezone": "Europe/Amsterdam", "locale": "nl-NL"},
    {"city": "London", "region": "England", "country": "GB", "latitude": 51.5074, "longitude": -0.1278, "timezone": "Europe/London", "locale": "en-GB"},
    {"city": "Paris", "region": "Ile-de-France", "country": "FR", "latitude": 48.8566, "longitude": 2.3522, "timezone": "Europe/Paris", "locale": "fr-FR"},
    {"city": "Madrid", "region": "Community of Madrid", "country": "ES", "latitude": 40.4168, "longitude": -3.7038, "timezone": "Europe/Madrid", "locale": "es-ES"},
    {"city": "Stockholm", "region": "Stockholm", "country": "SE", "latitude": 59.3293, "longitude": 18.0686, "timezone": "Europe/Stockholm", "locale": "sv-SE"},
    {"city": "Warsaw", "region": "Masovia", "country": "PL", "latitude": 52.2297, "longitude": 21.0122, "timezone": "Europe/Warsaw", "locale": "pl-PL"},
    {"city": "New York", "region": "New York", "country": "US", "latitude": 40.7128, "longitude": -74.0060, "timezone": "America/New_York", "locale": "en-US"},
    {"city": "Chicago", "region": "Illinois", "country": "US", "latitude": 41.8781, "longitude": -87.6298, "timezone": "America/Chicago", "locale": "en-US"},
    {"city": "Denver", "region": "Colorado", "country": "US", "latitude": 39.7392, "longitude": -104.9903, "timezone": "America/Denver", "locale": "en-US"},
    {"city": "San Francisco", "region": "California", "country": "US", "latitude": 37.7749, "longitude": -122.4194, "timezone": "America/Los_Angeles", "locale": "en-US"},
    {"city": "Toronto", "region": "Ontario", "country": "CA", "latitude": 43.6532, "longitude": -79.3832, "timezone": "America/Toronto", "locale": "en-CA"},
    {"city": "Sao Paulo", "region": "Sao Paulo", "country": "BR", "latitude": -23.5505, "longitude": -46.6333, "timezone": "America/Sao_Paulo", "locale": "pt-BR"},
    {"city": "Tokyo", "region": "Tokyo", "country": "JP", "latitude": 35.6762, "longitude": 139.6503, "timezone": "Asia/Tokyo", "locale": "ja-JP"},
    {"city": "Osaka", "region": "Osaka", "country": "JP", "latitude": 34.6937, "longitude": 135.5023, "timezone": "Asia/Tokyo", "locale": "ja-JP"},
    {"city": "Seoul", "region": "Seoul", "country": "KR", "latitude": 37.5665, "longitude": 126.9780, "timezone": "Asia/Seoul", "locale": "ko-KR"},
    {"city": "Singapore", "region": "Singapore", "country": "SG", "latitude": 1.3521, "longitude": 103.8198, "timezone": "Asia/Singapore", "locale": "en-SG"},
    {"city": "Mumbai", "region": "Maharashtra", "country": "IN", "latitude": 19.0760, "longitude": 72.8777, "timezone": "Asia/Kolkata", "locale": "en-IN"},
    {"city": "Sydney", "region": "New South Wales", "country": "AU", "latitude": -33.8688, "longitude": 151.2093, "timezone": "Australia/Sydney", "locale": "en-AU"},
    {"city": "Auckland", "region": "Auckland", "country": "NZ", "latitude": -36.8485, "longitude": 174.7633, "timezone": "Pacific/Auckland", "locale": "en-NZ"},
    {"city": "Dubai", "region": "Dubai", "country": "AE", "latitude": 25.2048, "longitude": 55.2708, "timezone": "Asia/Dubai", "locale": "en-AE"},
]


RESOLVERS = [
    ResolverProfile(
        identifier="cloudflare-doh",
        mode="doh",
        label="Cloudflare DNS over HTTPS",
        endpoints=["https://cloudflare-dns.com/dns-query"],
        fallback="refuse",
        bootstrap=["1.1.1.1"],
    ),
    ResolverProfile(
        identifier="quad9-doh",
        mode="doh",
        label="Quad9 DNS over HTTPS",
        endpoints=["https://dns.quad9.net/dns-query"],
        fallback="refuse",
        bootstrap=["9.9.9.9"],
    ),
    ResolverProfile(
        identifier="cloudflare-dot",
        mode="dot",
        label="Cloudflare DNS over TLS",
        servers=["1.1.1.1"],
        port=853,
        fallback="refuse",
    ),
    ResolverProfile(
        identifier="quad9-dot",
        mode="dot",
        label="Quad9 DNS over TLS",
        servers=["9.9.9.9"],
        port=853,
        fallback="refuse",
    ),
    ResolverProfile(
        identifier="local-plain",
        mode="custom",
        label="Local resolver, unencrypted",
        servers=["192.168.1.1"],
        port=53,
        fallback="refuse",
    ),
]


def default_profiles() -> list:
    """Profiles the application starts with.

    The initial state is deliberately conservative: automatic detection, the host
    clock, the browser default locale, the host resolver and the engine's own
    WebRTC behaviour. Nothing is virtualised until the user says so.
    """
    return [
        GeoProfile(
            identifier="default",
            name="Default environment",
            geolocation_mode="automatic",
            randomization="none",
            timezone_mode="automatic",
            locale_mode="system",
            dns_mode="system",
            dns_fallback="refuse",
            webrtc_policy="default",
            consent_mode="prompt",
            notes="The state the browser starts in. No virtualisation is applied before it is requested.",
        ),
        GeoProfile(
            identifier="berlin-wide",
            name="Berlin, wide radius",
            country="DE",
            region="Berlin",
            city="Berlin",
            latitude=52.5200,
            longitude=13.4050,
            radius_m=12000.0,
            timezone="Europe/Berlin",
            timezone_mode="profile",
            locale="en-US",
            locale_mode="profile",
            languages=["en-US", "de-DE"],
            geolocation_mode="virtual",
            randomization="stable",
            dns_mode="doh",
            dns_resolver="cloudflare-doh",
            dns_fallback="refuse",
            webrtc_policy="privacy_enhanced",
            consent_mode="prompt",
            notes="A wide radius keeps the reported position away from any single address.",
        ),
        GeoProfile(
            identifier="tokyo-precise",
            name="Tokyo, narrow radius",
            country="JP",
            region="Tokyo",
            city="Tokyo",
            latitude=35.6762,
            longitude=139.6503,
            radius_m=800.0,
            timezone="Asia/Tokyo",
            timezone_mode="profile",
            locale="ja-JP",
            locale_mode="profile",
            languages=["ja-JP", "en-US"],
            geolocation_mode="virtual",
            randomization="seeded",
            randomization_seed=20260930,
            dns_mode="dot",
            dns_resolver="quad9-dot",
            dns_fallback="refuse",
            webrtc_policy="disable_local_candidates",
            consent_mode="prompt",
            notes="A seeded narrow radius, reproducible across restarts for testing.",
        ),
        GeoProfile(
            identifier="london-hybrid",
            name="London, detected and constrained",
            country="GB",
            region="England",
            city="London",
            latitude=51.5074,
            longitude=-0.1278,
            radius_m=4000.0,
            timezone="Europe/London",
            timezone_mode="profile",
            locale="en-GB",
            locale_mode="profile",
            languages=["en-GB"],
            geolocation_mode="hybrid",
            randomization="session",
            dns_mode="doh",
            dns_resolver="quad9-doh",
            dns_fallback="refuse",
            webrtc_policy="privacy_enhanced",
            consent_mode="prompt",
            notes="The detected centre is kept; the city and radius are pinned by hand.",
        ),
        GeoProfile(
            identifier="no-location",
            name="Location withheld",
            geolocation_mode="disabled",
            timezone_mode="automatic",
            locale_mode="system",
            dns_mode="doh",
            dns_resolver="cloudflare-doh",
            dns_fallback="refuse",
            webrtc_policy="disable_local_candidates",
            consent_mode="deny",
            notes="Geolocation is refused outright rather than answered with a substitute position.",
        ),
    ]


DEFAULT_POLICIES = [
    SitePolicy(pattern="internal.example", scope="subdomain", profile="berlin-wide", notes="Development host pinned to the Berlin environment."),
    SitePolicy(pattern="localhost", scope="origin", profile="default", notes="Local development keeps the host environment."),
    SitePolicy(pattern="docs.example", scope="domain", timezone="UTC", locale="en-US", notes="Documentation is read on a fixed clock."),
]
