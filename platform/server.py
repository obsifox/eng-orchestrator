#!/usr/bin/env python3
"""Application server for the environment control center.

Standard library only, so the application runs wherever Python runs and has no
install step, no lockfile and no supply chain. The server exposes a JSON API over
the core and serves the interface from the same origin, which means the browser
never calls localhost, never calls a second port, and never needs a cross-origin
exception to work.

Binding to 0.0.0.0 is deliberate. The interface is reached through a preview host
rather than through the loopback address, so a server bound to 127.0.0.1 would be
unreachable from the browser that is supposed to display it.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import pathlib
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from core import ENGINE_VERSION, build_report
from core.catalog import CITIES, DEFAULT_POLICIES, RESOLVERS, default_profiles
from core.dns_engine import DnsEngine
from core.dns_engine import MODES as DNS_MODES
from core.environment import EnvironmentPipeline, SitePolicy
from core.errors import EnvironmentError, ProfileError
from core.geo import RANDOMIZATION_MODES
from core.host import HostDetector, describe
from core.locale_engine import LocaleEngine
from core.profiles import CURRENT_VERSION, GeoProfile, ProfileStore
from core.storage import PlatformStorage, load_into
from core.timezone_engine import TimezoneEngine, available_identifiers

UI_DIRECTORY = pathlib.Path(__file__).resolve().parent / "ui"
DEFAULT_DATA_DIRECTORY = pathlib.Path(__file__).resolve().parent / "data"

MAX_REQUEST_BYTES = 262144


class ApplicationState:
    """Everything the API reads, assembled once at start-up.

    Profiles come from disk when disk is available. The shipped defaults are
    seeded only into an empty store, so a user who deletes one of them does not
    find it resurrected on the next start.
    """

    def __init__(self, data_directory=None, persistent=None):
        self.host = describe()
        self.timezone_engine = TimezoneEngine(self.host["timezone"])
        self.locale_engine = LocaleEngine(self.host["locale"] or "en-US")
        self.resolvers = {resolver.identifier: resolver for resolver in RESOLVERS}
        self.detector = HostDetector(self.host)
        self.dns_engine = DnsEngine()
        self.store = ProfileStore()

        root = pathlib.Path(data_directory) if data_directory else DEFAULT_DATA_DIRECTORY
        self.storage = PlatformStorage(root, writable=persistent)
        self.load_result = load_into(self.store, self.storage)

        if len(self.store) == 0:
            for profile in default_profiles():
                self.store.add(profile)

            self.storage.save_all([self.store.get(name) for name in self.store.identifiers()])
            self.seeded = True
        else:
            self.seeded = False

        self.active_profile = str(self.storage.settings.get("active_profile") or "default-environment")

        if self.store.get(self.active_profile) is None:
            self.active_profile = self.store.identifiers()[0] if len(self.store) else "default-environment"

        self.policies = list(DEFAULT_POLICIES)

        self.pipeline = EnvironmentPipeline(
            timezone_engine=self.timezone_engine,
            locale_engine=self.locale_engine,
            dns_engine=self.dns_engine,
            resolvers=self.resolvers,
            detector=self.detector.__call__,
            physical_reader=None,
            policies=self.policies,
        )

        self.last_snapshot = None

    def profile(self, identifier: str) -> GeoProfile:
        if not identifier:
            identifier = self.active_profile

        found = self.store.get(identifier)

        if found is None:
            raise ProfileError(f"no profile named {identifier!r}", "the store does not hold this identifier")

        return found

    def snapshot(self, identifier: str, host: str, session: str) -> dict:
        snapshot = self.pipeline.run(self.profile(identifier), host=host or None, session_id=session)
        self.last_snapshot = snapshot

        return snapshot

    def activate(self, identifier: str) -> dict:
        profile = self.profile(identifier)
        self.active_profile = profile.identifier
        settings = self.storage.save_settings(active_profile=profile.identifier)

        return {"active_profile": profile.identifier, "persisted": self.storage.persistent, "settings": settings}

    def persist_profiles(self) -> None:
        self.storage.save_all([self.store.get(name) for name in self.store.identifiers()])

    def as_dict(self) -> dict:
        return {
            "engine_version": ENGINE_VERSION,
            "profile_version": CURRENT_VERSION,
            "host": self.host,
            "active_profile": self.active_profile,
            "storage": self.storage.summary(),
            "seeded": self.seeded,
            "last_load": self.load_result.as_dict(),
            "counts": {
                "profiles": len(self.store),
                "resolvers": len(self.resolvers),
                "policies": len(self.policies),
                "cities": len(CITIES),
                "timezones": len(available_identifiers()),
            },
        }


def build_handler(state: ApplicationState):
    class Handler(BaseHTTPRequestHandler):
        server_version = "EnvironmentCore/" + ENGINE_VERSION
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):
            sys.stderr.write("request %s\n" % (fmt % args))

        def send_json(self, payload, status=200):
            body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def send_error_json(self, message, status=400, detail=""):
            self.send_json({"error": message, "detail": detail}, status=status)

        def send_file(self, path):
            if not path.exists() or not path.is_file():
                self.send_error(404, "not found")
                return

            guessed, _ = mimetypes.guess_type(str(path))
            body = path.read_bytes()

            if path.suffix == ".js":
                content_type = "text/javascript; charset=utf-8"
            elif path.suffix == ".css":
                content_type = "text/css; charset=utf-8"
            elif path.suffix == ".html":
                content_type = "text/html; charset=utf-8"
            else:
                content_type = (guessed or "application/octet-stream") + "; charset=utf-8"

            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def resolved_path(self):
            parsed = urllib.parse.urlparse(self.path)
            route = parsed.path
            query = urllib.parse.parse_qs(parsed.query)

            def one(name, default=""):
                values = query.get(name)
                return values[0] if values else default

            return route, one

        def do_GET(self):
            try:
                self.route_get()
            except EnvironmentError as error:
                self.send_error_json(error.message, status=400, detail=error.detail)
            except Exception as error:
                self.send_error_json("unhandled error", status=500, detail=str(error))

        def route_get(self):
            route, one = self.resolved_path()

            if route in ("/", "/index.html"):
                self.send_file(UI_DIRECTORY / "index.html")
                return

            if route.startswith("/ui/"):
                candidate = (UI_DIRECTORY / route[len("/ui/"):]).resolve()

                if not str(candidate).startswith(str(UI_DIRECTORY.resolve())):
                    self.send_error_json("path escapes the interface directory", status=403)
                    return

                self.send_file(candidate)
                return

            if route == "/api/meta":
                self.send_json(state.as_dict())
                return

            if route == "/api/host":
                self.send_json(state.host)
                return

            if route == "/api/environment":
                snapshot = state.snapshot(one("profile", "default-environment"), one("host"), one("session", "preview"))
                self.send_json(snapshot)
                return

            if route == "/api/profiles":
                listing = []

                for identifier in state.store.identifiers():
                    profile = state.store.get(identifier)
                    entry = profile.as_dict()
                    entry["valid_checksum"] = profile.verify_checksum()
                    listing.append(entry)

                self.send_json({"profiles": listing, "profile_version": CURRENT_VERSION})
                return

            if route.startswith("/api/profiles/"):
                remainder = route[len("/api/profiles/"):]

                if remainder.endswith("/export"):
                    identifier = remainder[: -len("/export")]
                    self.send_json(state.store.export(identifier))
                    return

                profile = state.store.get(remainder)

                if profile is None:
                    self.send_error_json(f"no profile named {remainder!r}", status=404)
                    return

                payload = profile.as_dict()
                payload["valid_checksum"] = profile.verify_checksum()
                self.send_json(payload)
                return

            if route == "/api/resolvers":
                self.send_json({"resolvers": [resolver.as_dict() for resolver in state.resolvers.values()]})
                return

            if route == "/api/policies":
                self.send_json({"policies": [policy.as_dict() for policy in state.policies]})
                return

            if route == "/api/locations":
                term = one("q").strip().lower()
                matches = [
                    city
                    for city in CITIES
                    if not term or term in city["city"].lower() or term in city["country"].lower() or term in city["region"].lower()
                ]
                self.send_json({"locations": matches, "total": len(CITIES), "source": "offline catalogue"})
                return

            if route == "/api/timezones":
                term = one("q").strip().lower()
                identifiers = available_identifiers()
                matches = [name for name in identifiers if not term or term in name.lower()]

                self.send_json({"timezones": matches[:200], "total": len(matches), "truncated": len(matches) > 200})
                return

            if route == "/api/dns-modes":
                self.send_json({"modes": list(DNS_MODES), "randomization_modes": list(RANDOMIZATION_MODES)})
                return

            if route == "/api/diagnostics":
                snapshot = state.last_snapshot if state.last_snapshot else state.snapshot("default-environment", "", "preview")
                level = one("level", "redacted")
                report = build_report(snapshot, level=level, engine_version=ENGINE_VERSION)

                if one("persist") == "true":
                    path = state.storage.write_diagnostic(report, level)
                    report["written_to"] = path.name if path.name else ""
                    state.storage.prune_diagnostics(keep=20)

                self.send_json(report)
                return

            if route == "/api/diagnostics/list":
                self.send_json({"exports": state.storage.list_diagnostics(), "persistent": state.storage.persistent})
                return

            self.send_error_json(f"no route for {route}", status=404)

        def do_POST(self):
            try:
                self.route_post()
            except EnvironmentError as error:
                self.send_error_json(error.message, status=400, detail=error.detail)
            except Exception as error:
                self.send_error_json("unhandled error", status=500, detail=str(error))

        def route_post(self):
            route, _one = self.resolved_path()

            length = int(self.headers.get("Content-Length") or 0)

            if length > MAX_REQUEST_BYTES:
                self.send_error_json("request body is too large", status=413)
                return

            raw = self.rfile.read(length) if length else b"{}"

            try:
                payload = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                self.send_error_json("request body is not valid JSON", status=400, detail=str(error))
                return

            if route == "/api/profiles/import":
                strict = bool(payload.get("strict", True))
                require_checksum = bool(payload.get("require_checksum", False))
                body = payload.get("profile", payload)

                profile = state.store.import_payload(body, strict=strict, require_checksum=require_checksum)
                state.storage.save_profile(profile)
                state.persist_profiles()

                self.send_json(
                    {
                        "imported": profile.identifier,
                        "migrations": profile.migrations,
                        "checksum": profile.checksum,
                        "validated": True,
                        "persisted": state.storage.persistent,
                    },
                    status=201,
                )
                return

            if route == "/api/settings":
                allowed = {"active_profile", "redaction_level", "session_id", "interface"}
                changes = {key: value for key, value in payload.items() if key in allowed}

                if not changes:
                    self.send_error_json("no recognised settings in the request", status=400)
                    return

                if "active_profile" in changes:
                    profile = state.profile(str(changes["active_profile"]))
                    changes["active_profile"] = profile.identifier
                    state.active_profile = profile.identifier

                settings = state.storage.save_settings(**changes)
                self.send_json({"settings": settings, "persistent": state.storage.persistent})
                return

            if route == "/api/profiles/activate":
                self.send_json(state.activate(str(payload.get("identifier", ""))))
                return

            if route == "/api/profiles/validate":
                body = payload.get("profile", payload)
                problems = []

                try:
                    candidate = GeoProfile.from_payload(body, strict=bool(payload.get("strict", True)))
                    checksum_ok = candidate.verify_checksum()
                except EnvironmentError as error:
                    problems = [error.detail or error.message]
                    candidate = None
                    checksum_ok = False

                self.send_json(
                    {
                        "valid": not problems,
                        "problems": problems,
                        "identifier": candidate.identifier if candidate else None,
                        "checksum_valid": checksum_ok,
                    }
                )
                return

            if route == "/api/profiles/delete":
                identifier = str(payload.get("identifier", ""))

                if identifier == state.active_profile:
                    self.send_error_json(
                        "the active profile cannot be deleted",
                        status=409,
                        detail="activate a different profile first, so the environment is never left undefined",
                    )
                    return

                removed = state.store.remove(identifier)
                state.storage.delete_profile(identifier)
                state.persist_profiles()

                self.send_json({"removed": removed, "persisted": state.storage.persistent}, status=200 if removed else 404)
                return

            if route == "/api/policies/add":
                policy = SitePolicy(
                    pattern=str(payload.get("pattern", "")),
                    scope=str(payload.get("scope", "domain")),
                    profile=payload.get("profile"),
                    timezone=payload.get("timezone"),
                    locale=payload.get("locale"),
                    dns_mode=payload.get("dns_mode"),
                    notes=str(payload.get("notes", "")),
                )

                if not policy.pattern:
                    self.send_error_json("a policy needs a pattern", status=400)
                    return

                policy.matches("example.com")

                state.policies.append(policy)
                self.send_json({"added": policy.as_dict()}, status=201)
                return

            self.send_error_json(f"no route for {route}", status=404)

    return Handler


def main() -> int:
    parser = argparse.ArgumentParser(description="Environment control center server.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8770)
    args = parser.parse_args()

    state = ApplicationState()
    handler = build_handler(state)

    server = ThreadingHTTPServer((args.host, args.port), handler)
    server.daemon_threads = True

    print(f"environment control center listening on {args.host}:{args.port}", flush=True)
    print(f"host timezone {state.host['timezone']}, locale {state.host['locale']}", flush=True)
    print(f"profiles {len(state.store)}, resolvers {len(state.resolvers)}, timezones {len(available_identifiers())}", flush=True)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("stopping", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
