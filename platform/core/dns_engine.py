"""DNS engine: browser-scoped name resolution.

The single most important property of this module is what it cannot do. It
produces a resolution plan for the browser. It does not write
/etc/resolv.conf, it does not call a system resolver configuration API, it does
not touch a router, and it does not affect any other application. That
limitation is enforced by construction rather than by convention: the module
imports no networking library and holds no file handle. A name lookup performed
here would be a lie about the architecture, so the engine plans and validates,
and the browser's own network stack is what would eventually act.

Every plan states which protocol would be used and whether it has a fallback.
An implicit fallback is the failure mode this design is written to avoid: a user
who selected DNS-over-TLS must not silently end up on the system resolver.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from .errors import InvalidResolverError

MODE_SYSTEM = "system"
MODE_CUSTOM = "custom"
MODE_DOH = "doh"
MODE_DOT = "dot"

MODES = (MODE_SYSTEM, MODE_CUSTOM, MODE_DOH, MODE_DOT)

PROTOCOL_LABELS = {
    MODE_SYSTEM: "system resolver",
    MODE_CUSTOM: "plain DNS to a named server",
    MODE_DOH: "DNS over HTTPS",
    MODE_DOT: "DNS over TLS",
}

FALLBACK_REFUSE = "refuse"
FALLBACK_SYSTEM = "system"
FALLBACK_CUSTOM = "custom"

FALLBACKS = (FALLBACK_REFUSE, FALLBACK_SYSTEM, FALLBACK_CUSTOM)

HOSTNAME_PATTERN = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*$")
IPV4_PATTERN = re.compile(r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$")

DEFAULT_DOH_ENDPOINTS = {
    "cloudflare": "https://cloudflare-dns.com/dns-query",
    "quad9": "https://dns.quad9.net/dns-query",
    "google": "https://dns.google/dns-query",
}

DEFAULT_DOT_HOSTS = {
    "cloudflare": ("1.1.1.1", 853),
    "quad9": ("9.9.9.9", 853),
    "google": ("8.8.8.8", 853),
}

INSECURE_PORTS = (853, 443)
PLAINTEXT_DNS_PORT = 53


def validate_hostname(value: str, field_name: str = "hostname") -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidResolverError(f"{field_name} must be a non-empty string", f"received {value!r}")

    candidate = value.strip()

    if len(candidate) > 253:
        raise InvalidResolverError(f"{field_name} is longer than the 253 character limit", f"received {len(candidate)}")

    if not HOSTNAME_PATTERN.match(candidate):
        raise InvalidResolverError(f"{field_name} is not a valid hostname", f"received {candidate!r}")

    return candidate.lower()


def validate_ipv4(value: str, field_name: str = "address") -> str:
    match = IPV4_PATTERN.match(str(value).strip())

    if not match:
        raise InvalidResolverError(f"{field_name} is not a dotted-quad IPv4 address", f"received {value!r}")

    for group in match.groups():
        if int(group) > 255:
            raise InvalidResolverError(f"{field_name} has an octet above 255", f"received {value!r}")

    return str(value).strip()


def validate_port(value, field_name: str = "port") -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        try:
            value = int(value)
        except (TypeError, ValueError) as error:
            raise InvalidResolverError(f"{field_name} must be an integer", f"received {value!r}") from error

    if not 1 <= value <= 65535:
        raise InvalidResolverError(f"{field_name} must be between 1 and 65535", f"received {value}")

    return value


def validate_doh_endpoint(url: str) -> str:
    """Validate a DNS-over-HTTPS endpoint.

    The endpoint must be HTTPS. A plaintext endpoint behind a name that suggests
    encryption is worse than an honest plaintext one, because the user has no way
    to tell the difference from the interface.
    """
    if not isinstance(url, str) or not url.strip():
        raise InvalidResolverError("endpoint must be a non-empty string", f"received {url!r}")

    candidate = url.strip()

    if not candidate.lower().startswith("https://"):
        scheme = candidate.split("://", 1)[0] if "://" in candidate else "none"
        raise InvalidResolverError(
            "endpoint must use HTTPS",
            f"received scheme {scheme!r}, which would not protect the query",
        )

    remainder = candidate[len("https://"):]

    if not remainder:
        raise InvalidResolverError("endpoint has no host", f"received {candidate!r}")

    host = remainder.split("/", 1)[0]

    if ":" in host:
        host, _, port_text = host.partition(":")
        validate_port(port_text, "endpoint port")

    validate_hostname(host, "endpoint host")

    return candidate


@dataclass
class ResolverProfile:
    """A named resolver configuration that a geo profile can reference."""

    identifier: str
    mode: str
    label: str = ""
    endpoints: list = field(default_factory=list)
    servers: list = field(default_factory=list)
    port: int = PLAINTEXT_DNS_PORT
    fallback: str = FALLBACK_REFUSE
    validate_certificate: bool = True
    bootstrap: list = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "identifier": self.identifier,
            "mode": self.mode,
            "label": self.label or self.identifier,
            "endpoints": list(self.endpoints),
            "servers": list(self.servers),
            "port": self.port,
            "fallback": self.fallback,
            "validate_certificate": self.validate_certificate,
            "bootstrap": list(self.bootstrap),
        }


@dataclass
class DnsResolution:
    """The resolution plan, with the guarantees and the caveats attached."""

    mode: str
    protocol: str
    endpoints: list = field(default_factory=list)
    servers: list = field(default_factory=list)
    port: int = PLAINTEXT_DNS_PORT
    encrypted: bool = False
    certificate_validated: bool = False
    fallback: str = FALLBACK_REFUSE
    fallback_protocol: str = ""
    affects_operating_system: bool = False
    source: str = "profile"
    confidence: str = "configured"
    detail: str = ""

    def as_dict(self) -> dict:
        return {
            "mode": self.mode,
            "protocol": self.protocol,
            "endpoints": list(self.endpoints),
            "servers": list(self.servers),
            "port": self.port,
            "encrypted": self.encrypted,
            "certificate_validated": self.certificate_validated,
            "fallback": self.fallback,
            "fallback_protocol": self.fallback_protocol,
            "affects_operating_system": self.affects_operating_system,
            "source": self.source,
            "confidence": self.confidence,
            "detail": self.detail,
        }


class DnsEngine:
    """Builds and validates a browser-scoped resolution plan."""

    def __init__(self, system_servers: Optional[list] = None, system_encrypted: bool = False):
        self.system_servers = list(system_servers or [])
        self.system_encrypted = bool(system_encrypted)

    def resolve(self, mode: str, resolver: Optional[ResolverProfile] = None, fallback: str = FALLBACK_REFUSE) -> DnsResolution:
        if mode not in MODES:
            raise InvalidResolverError(f"unknown DNS mode {mode!r}", f"expected one of {MODES}")

        if fallback not in FALLBACKS:
            raise InvalidResolverError(f"unknown fallback policy {fallback!r}", f"expected one of {FALLBACKS}")

        if mode == MODE_SYSTEM:
            return DnsResolution(
                mode=mode,
                protocol=PROTOCOL_LABELS[mode],
                servers=list(self.system_servers),
                encrypted=self.system_encrypted,
                certificate_validated=self.system_encrypted,
                fallback=FALLBACK_REFUSE,
                source="host",
                confidence="measured",
                detail="the host resolver is used as-is and is not modified",
            )

        if resolver is None:
            raise InvalidResolverError(
                f"mode {mode!r} requires a resolver profile",
                "no resolver was supplied, and there is no safe default to invent",
            )

        effective_fallback = resolver.fallback or fallback

        if effective_fallback not in FALLBACKS:
            raise InvalidResolverError(f"resolver {resolver.identifier!r} has an unknown fallback policy", f"received {effective_fallback!r}")

        fallback_protocol = {
            FALLBACK_REFUSE: "",
            FALLBACK_SYSTEM: "system resolver, in plaintext",
            FALLBACK_CUSTOM: "the resolver servers, in plaintext",
        }[effective_fallback]

        if mode == MODE_CUSTOM:
            if not resolver.servers:
                raise InvalidResolverError("a custom resolver needs at least one server", f"resolver {resolver.identifier!r} lists none")

            servers = [validate_ipv4(server) for server in resolver.servers]

            return DnsResolution(
                mode=mode,
                protocol=PROTOCOL_LABELS[mode],
                servers=servers,
                port=validate_port(resolver.port),
                encrypted=False,
                certificate_validated=False,
                fallback=effective_fallback,
                fallback_protocol=fallback_protocol,
                source="profile",
                confidence="configured",
                detail="queries leave the browser unencrypted, which is weaker than DoH or DoT",
            )

        if mode == MODE_DOH:
            if not resolver.endpoints:
                raise InvalidResolverError("a DNS-over-HTTPS resolver needs at least one endpoint", f"resolver {resolver.identifier!r} lists none")

            endpoints = [validate_doh_endpoint(endpoint) for endpoint in resolver.endpoints]

            return DnsResolution(
                mode=mode,
                protocol=PROTOCOL_LABELS[mode],
                endpoints=endpoints,
                encrypted=True,
                certificate_validated=bool(resolver.validate_certificate),
                fallback=effective_fallback,
                fallback_protocol=fallback_protocol,
                source="profile",
                confidence="configured",
                detail=(
                    "certificate validation is on"
                    if resolver.validate_certificate
                    else "certificate validation is off, which defeats the purpose of an encrypted transport"
                ),
            )

        if not resolver.servers and not resolver.endpoints:
            raise InvalidResolverError("a DNS-over-TLS resolver needs a server or a hostname", f"resolver {resolver.identifier!r} lists neither")

        servers = []

        for server in resolver.servers:
            servers.append(validate_ipv4(server))

        hosts = [validate_hostname(endpoint) for endpoint in resolver.endpoints]

        return DnsResolution(
            mode=mode,
            protocol=PROTOCOL_LABELS[mode],
            servers=servers,
            endpoints=[f"{host}:{validate_port(resolver.port)}" for host in hosts],
            port=validate_port(resolver.port),
            encrypted=True,
            certificate_validated=bool(resolver.validate_certificate),
            fallback=effective_fallback,
            fallback_protocol=fallback_protocol,
            source="profile",
            confidence="configured",
            detail=(
                "the server name is validated against the certificate presented"
                if resolver.validate_certificate
                else "certificate validation is off, so the transport is encrypted but unauthenticated"
            ),
        )
