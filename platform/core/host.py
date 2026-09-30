"""Host signals: what the machine reports, read without guessing.

Nothing here changes the host. The module reads environment variables and a
small number of world-readable files so that automatic mode has something to work
with, and so that the interface can show the user what the browser inherited
before they overrode anything.

Detection from these signals is weak, and the code says so. A timezone implies a
longitude band and a coarse latitude guess, not a city. Returning a country-sized
radius alongside a low confidence is the honest representation of that, and it is
what the diagnostics screen displays rather than a precise-looking pin.
"""

from __future__ import annotations

import os
import platform
import socket
import sys
from datetime import datetime, timezone as dt_timezone
from typing import Optional

from .timezone_engine import is_valid_identifier, normalise

COUNTRY_BY_TIMEZONE_PREFIX = {
    "Europe/Berlin": "DE",
    "Europe/Amsterdam": "NL",
    "Europe/London": "GB",
    "Europe/Paris": "FR",
    "Europe/Madrid": "ES",
    "Europe/Stockholm": "SE",
    "Europe/Warsaw": "PL",
    "Europe/Rome": "IT",
    "Europe/Dublin": "IE",
    "Europe/Lisbon": "PT",
    "America/New_York": "US",
    "America/Chicago": "US",
    "America/Denver": "US",
    "America/Los_Angeles": "US",
    "America/Toronto": "CA",
    "America/Sao_Paulo": "BR",
    "Asia/Tokyo": "JP",
    "Asia/Seoul": "KR",
    "Asia/Singapore": "SG",
    "Asia/Kolkata": "IN",
    "Asia/Dubai": "AE",
    "Asia/Shanghai": "CN",
    "Australia/Sydney": "AU",
    "Pacific/Auckland": "NZ",
}

COUNTRY_CENTROID = {
    "DE": (51.1657, 10.4515),
    "NL": (52.1326, 5.2913),
    "GB": (54.0, -2.0),
    "FR": (46.2276, 2.2137),
    "ES": (40.4637, -3.7492),
    "SE": (60.1282, 18.6435),
    "PL": (51.9194, 19.1451),
    "IT": (41.8719, 12.5674),
    "IE": (53.4129, -8.2439),
    "PT": (39.3999, -8.2245),
    "US": (39.8283, -98.5795),
    "CA": (56.1304, -106.3468),
    "BR": (-14.2350, -51.9253),
    "JP": (36.2048, 138.2529),
    "KR": (35.9078, 127.7669),
    "SG": (1.3521, 103.8198),
    "IN": (20.5937, 78.9629),
    "AE": (23.4241, 53.8478),
    "CN": (35.8617, 104.1954),
    "AU": (-25.2744, 133.7751),
    "NZ": (-40.9006, 174.8860),
}

COUNTRY_RADIUS_M = 700000.0


def environment_variable(name: str, default: str = "") -> str:
    return str(os.environ.get(name, default) or default)


def system_timezone() -> tuple:
    """The timezone the host is in, and how that was determined."""
    for variable in ("TZ", "TIMEZONE"):
        candidate = environment_variable(variable)

        if candidate and is_valid_identifier(candidate):
            return normalise(candidate).strip(":"), f"environment variable {variable}"

    localtime = "/etc/localtime"

    try:
        if os.path.islink(localtime):
            target = os.readlink(localtime)
            marker = "zoneinfo/"
            if marker in target:
                candidate = target.split(marker, 1)[1]
                if is_valid_identifier(candidate):
                    return candidate, "the /etc/localtime symbolic link"
    except OSError:
        pass

    for path in ("/etc/timezone", "/var/db/zoneinfo"):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                candidate = handle.read().strip()
            if candidate and is_valid_identifier(candidate):
                return candidate, path
        except OSError:
            continue

    return "UTC", "no host timezone could be read, so UTC is assumed"


def system_locale() -> tuple:
    """The locale the host reports, and which variables supplied it."""
    for variable in ("LC_ALL", "LC_MESSAGES", "LANG"):
        candidate = environment_variable(variable)

        if candidate:
            return candidate, f"environment variable {variable}"

    return "en-US", "no locale variable was set, so a neutral default is reported"


def network_summary() -> dict:
    """A coarse description of the host network, without probing it.

    The hostname and a local address are read from the socket layer. No packet is
    sent anywhere, which matters because this function runs on a page the user
    opened to configure privacy, not to disclose it.
    """
    summary = {
        "hostname": "",
        "has_ipv4": False,
        "has_ipv6": False,
        "interface_count": 0,
        "proxy_configured": False,
    }

    try:
        summary["hostname"] = socket.gethostname()
    except OSError:
        summary["hostname"] = ""

    try:
        for entry in socket.getaddrinfo(socket.gethostname(), None):
            family = entry[0]
            if family == socket.AF_INET:
                summary["has_ipv4"] = True
            elif family == socket.AF_INET6:
                summary["has_ipv6"] = True
    except (OSError, socket.gaierror):
        pass

    for variable in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        if environment_variable(variable):
            summary["proxy_configured"] = True
            break

    try:
        interfaces = os.listdir("/sys/class/net")
        summary["interface_count"] = len([name for name in interfaces if name != "lo"])
    except OSError:
        summary["interface_count"] = 0

    return summary


def describe() -> dict:
    """A snapshot of the host, for the interface and for diagnostics."""
    identifier, timezone_source = system_timezone()
    locale_value, locale_source = system_locale()

    return {
        "platform": sys.platform,
        "platform_release": platform.release(),
        "python_version": platform.python_version(),
        "timezone": identifier,
        "timezone_source": timezone_source,
        "locale": locale_value,
        "locale_source": locale_source,
        "network": network_summary(),
        "observed_at": datetime.now(dt_timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }


def timezone_country(identifier: str) -> Optional[str]:
    return COUNTRY_BY_TIMEZONE_PREFIX.get(normalise(identifier) if is_valid_identifier(identifier) else identifier)


class HostDetector:
    """Turns host signals into a proposed centre, with the weakness stated.

    The result is labelled derived and carries a country-sized radius, because a
    timezone identifies a band of the globe and not a position within it. A
    detector that returned a city coordinate here would be inventing precision it
    does not have.
    """

    def __init__(self, host_description: Optional[dict] = None):
        self.host = host_description or describe()

    def __call__(self, context: Optional[dict] = None) -> dict:
        identifier = self.host.get("timezone", "UTC")
        signals = []

        if self.host.get("timezone_source"):
            signals.append(f"timezone from {self.host['timezone_source']}")

        if self.host.get("locale_source"):
            signals.append(f"locale from {self.host['locale_source']}")

        network = self.host.get("network") or {}

        if network.get("proxy_configured"):
            signals.append("a proxy variable is set in the environment")

        if network.get("has_ipv6"):
            signals.append("the host resolves an IPv6 address")

        country = timezone_country(identifier)

        if country is None:
            return {
                "latitude": 0.0,
                "longitude": 0.0,
                "radius_m": 20000000.0,
                "country": None,
                "confidence": "low",
                "signals": signals,
                "reason": (
                    f"timezone {identifier} maps to no country in the offline table, "
                    "so no useful centre can be proposed"
                ),
            }

        latitude, longitude = COUNTRY_CENTROID[country]

        return {
            "latitude": latitude,
            "longitude": longitude,
            "radius_m": COUNTRY_RADIUS_M,
            "country": country,
            "confidence": "low",
            "signals": signals,
            "reason": (
                f"derived from timezone {identifier}, which identifies a country and not a position. "
                "The centre is the country centroid and the radius covers the whole country."
            ),
        }
