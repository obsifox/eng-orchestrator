"""Test suite for the environment core.

Runs on the standard library alone, so the suite works wherever the application
works. Every assertion either calls the code under test or reads a value it
produced; nothing asserts on a constant that was typed twice.

Run with:
    python3 -m unittest discover -s platform/tests -v
or:
    platform/run_tests.sh
"""

from __future__ import annotations

import json
import pathlib
import sys
import unittest
from datetime import datetime, timezone as dt_timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from core.catalog import DEFAULT_POLICIES, RESOLVERS, default_profiles
from core.diagnostics import (
    REDACTION_MINIMAL,
    REDACTION_REDACTED,
    analyse,
    build_report,
    redact_ipv4,
    redact_snapshot,
)
from core.dns_engine import (
    FALLBACK_REFUSE,
    DnsEngine,
    ResolverProfile,
    validate_doh_endpoint,
    validate_hostname,
    validate_ipv4,
)
from core.environment import (
    STATE_ERROR,
    STATE_MANUAL,
    EnvironmentPipeline,
    SitePolicy,
    resolve_policy,
)
from core.errors import (
    InvalidCoordinateError,
    InvalidRadiusError,
    InvalidResolverError,
    ProfileImportError,
    ProfileSchemaError,
    ProfileVersionError,
    StorageError,
    UnknownTimezoneError,
)
from core.geo import (
    RANDOMIZATION_SEEDED,
    RANDOMIZATION_STABLE,
    GeoArea,
    GeoEngine,
    PhysicalProvider,
    VirtualProvider,
    destination_point,
    haversine_m,
    validate_coordinate,
    validate_radius,
)
from core.locale_engine import LocaleEngine, build_accept_language, normalise_language_tag
from core.profiles import CURRENT_VERSION, GeoProfile, ProfileStore, compute_checksum, migrate
from core.storage import PlatformStorage, atomic_write, load_into, serialise
from core.timezone_engine import (
    TimezoneEngine,
    format_offset,
    is_valid_identifier,
    offset_minutes,
    plausibility,
)

BERLIN = (52.5200, 13.4050)


def test_detector(_context):
    return {
        "latitude": 52.5200,
        "longitude": 13.4050,
        "radius_m": 25000.0,
        "country": "DE",
        "confidence": "low",
        "reason": "test detector",
    }


def build_pipeline(detector=None, policies=None):
    return EnvironmentPipeline(
        timezone_engine=TimezoneEngine("Europe/Berlin"),
        locale_engine=LocaleEngine("en-US"),
        dns_engine=DnsEngine(),
        resolvers={resolver.identifier: resolver for resolver in RESOLVERS},
        detector=detector,
        policies=policies if policies is not None else list(DEFAULT_POLICIES),
    )


class CoordinateValidation(unittest.TestCase):

    def test_accepts_valid_coordinates(self):
        self.assertEqual(validate_coordinate(52.52, 13.405), (52.52, 13.405))
        self.assertEqual(validate_coordinate(-90, -180), (-90.0, -180.0))
        self.assertEqual(validate_coordinate(0, 0), (0.0, 0.0))

    def test_rejects_latitude_beyond_the_pole(self):
        with self.assertRaises(InvalidCoordinateError):
            validate_coordinate(90.1, 0)

    def test_rejects_longitude_beyond_the_antimeridian(self):
        with self.assertRaises(InvalidCoordinateError):
            validate_coordinate(0, 180.1)

    def test_rejects_non_numeric_and_boolean(self):
        for value in ("52.5", None, True, [52.5]):
            with self.assertRaises(InvalidCoordinateError):
                validate_coordinate(value, 0)

    def test_rejects_non_finite(self):
        for value in (float("nan"), float("inf")):
            with self.assertRaises(InvalidCoordinateError):
                validate_coordinate(value, 0)

    def test_radius_rejects_negative_and_absurd(self):
        with self.assertRaises(InvalidRadiusError):
            validate_radius(-1)
        with self.assertRaises(InvalidRadiusError):
            validate_radius(2000001)
        self.assertEqual(validate_radius(0), 0.0)
        self.assertEqual(validate_radius(5000), 5000.0)


class RadiusSampling(unittest.TestCase):

    def test_stable_mode_is_reproducible(self):
        area = GeoArea(BERLIN[0], BERLIN[1], 5000)
        engine = GeoEngine(VirtualProvider(area, RANDOMIZATION_STABLE), area)
        first = engine.resolve({"profile_id": "berlin"})
        second = engine.resolve({"profile_id": "berlin"})
        self.assertEqual(first.latitude, second.latitude)
        self.assertEqual(first.longitude, second.longitude)
        self.assertEqual(first.seed, second.seed)

    def test_stable_mode_differs_between_profiles(self):
        area = GeoArea(BERLIN[0], BERLIN[1], 5000)
        engine = GeoEngine(VirtualProvider(area, RANDOMIZATION_STABLE), area)
        first = engine.resolve({"profile_id": "one"})
        second = engine.resolve({"profile_id": "two"})
        self.assertNotEqual(first.seed, second.seed)

    def test_seeded_mode_is_reproducible_across_engines(self):
        area = GeoArea(BERLIN[0], BERLIN[1], 5000)
        first = GeoEngine(VirtualProvider(area, RANDOMIZATION_SEEDED, seed=42), area).resolve({})
        second = GeoEngine(VirtualProvider(area, RANDOMIZATION_SEEDED, seed=42), area).resolve({})
        self.assertEqual(first.latitude, second.latitude)
        self.assertEqual(first.longitude, second.longitude)

    def test_every_sample_stays_inside_the_radius(self):
        area = GeoArea(BERLIN[0], BERLIN[1], 7500)

        for seed in range(400):
            location = GeoEngine(VirtualProvider(area, RANDOMIZATION_SEEDED, seed=seed), area).resolve({})
            drift = haversine_m(BERLIN[0], BERLIN[1], location.latitude, location.longitude)
            self.assertLessEqual(drift, 7500.0 + 1.0)

    def test_distribution_is_uniform_over_the_disc_not_over_the_radius(self):
        radius = 10000.0
        area = GeoArea(BERLIN[0], BERLIN[1], radius)
        distances = []

        for seed in range(1500):
            location = GeoEngine(VirtualProvider(area, RANDOMIZATION_SEEDED, seed=seed), area).resolve({})
            distances.append(haversine_m(BERLIN[0], BERLIN[1], location.latitude, location.longitude))

        mean_fraction = (sum(distances) / len(distances)) / radius

        self.assertAlmostEqual(mean_fraction, 2.0 / 3.0, delta=0.035)
        self.assertGreater(max(distances) / radius, 0.95)

    def test_zero_radius_returns_the_centre(self):
        area = GeoArea(BERLIN[0], BERLIN[1], 0)
        location = GeoEngine(VirtualProvider(area, RANDOMIZATION_STABLE), area).resolve({})
        self.assertEqual(location.latitude, BERLIN[0])
        self.assertEqual(location.longitude, BERLIN[1])
        self.assertIsNone(location.seed)

    def test_destination_point_at_zero_distance_is_the_origin(self):
        latitude, longitude = destination_point(BERLIN[0], BERLIN[1], 0.0, 1.0)
        self.assertAlmostEqual(latitude, BERLIN[0], places=9)
        self.assertAlmostEqual(longitude, BERLIN[1], places=9)

    def test_haversine_matches_a_known_distance(self):
        distance = haversine_m(51.5074, -0.1278, 48.8566, 2.3522)
        self.assertAlmostEqual(distance, 343500, delta=3000)


class ProviderBehaviour(unittest.TestCase):

    def test_virtual_marks_itself_as_configured_not_measured(self):
        area = GeoArea(BERLIN[0], BERLIN[1], 1000)
        location = GeoEngine(VirtualProvider(area, RANDOMIZATION_STABLE), area).resolve({})
        self.assertEqual(location.source, "virtual")
        self.assertEqual(location.confidence, "configured")

    def test_physical_provider_without_a_reader_refuses(self):
        area = GeoArea(BERLIN[0], BERLIN[1], 0)
        with self.assertRaises(Exception) as caught:
            GeoEngine(PhysicalProvider(None), area).resolve({})
        self.assertIn("no physical location source", str(caught.exception))

    def test_disabled_provider_refuses_rather_than_substituting(self):
        area = GeoArea(BERLIN[0], BERLIN[1], 0)
        profile = GeoProfile(identifier="off", name="Off", geolocation_mode="disabled")
        pipeline = build_pipeline()
        snapshot = pipeline.run(profile)
        self.assertEqual(snapshot["state"], STATE_ERROR)
        self.assertEqual(snapshot["failed_stage"], "geo_resolution")
        self.assertIsNone(snapshot["geo"])

    def test_a_failed_geo_stage_never_substitutes_a_physical_location(self):
        import json

        profile = GeoProfile(
            identifier="hybrid-fail",
            name="Configured environment with no detector",
            geolocation_mode="hybrid",
            latitude=BERLIN[0],
            longitude=BERLIN[1],
            radius_m=100.0,
        )

        snapshot = build_pipeline(detector=None).run(profile)

        self.assertEqual(snapshot["state"], STATE_ERROR)
        self.assertIsNone(snapshot["geo"])
        self.assertNotIn("physical", json.dumps(snapshot))

        stage = [item for item in snapshot["stages"] if item["name"] == "geo_resolution"][0]
        self.assertEqual(stage["status"], "failed")
        self.assertTrue(any("no fallback provider was consulted" in note for note in stage["notes"]))


class TimezoneBehaviour(unittest.TestCase):

    def test_known_offsets_are_correct_for_a_fixed_instant(self):
        moment = datetime(2026, 1, 15, 12, 0, tzinfo=dt_timezone.utc)
        self.assertEqual(offset_minutes("Europe/Berlin", moment), 60)
        self.assertEqual(offset_minutes("Asia/Tokyo", moment), 540)
        self.assertEqual(offset_minutes("UTC", moment), 0)
        self.assertEqual(offset_minutes("Asia/Tehran", moment), 210)

    def test_daylight_saving_is_detected_in_summer_and_not_in_winter(self):
        engine = TimezoneEngine("Europe/Berlin")
        winter = engine.resolve("Europe/Berlin", "manual", datetime(2026, 1, 15, tzinfo=dt_timezone.utc))
        summer = engine.resolve("Europe/Berlin", "manual", datetime(2026, 7, 15, tzinfo=dt_timezone.utc))
        self.assertFalse(winter.daylight_saving)
        self.assertTrue(summer.daylight_saving)

    def test_rejects_unknown_identifier(self):
        with self.assertRaises(UnknownTimezoneError):
            TimezoneEngine("UTC").resolve("Mars/Olympus", "manual")

    def test_accepts_utc_in_any_case(self):
        self.assertTrue(is_valid_identifier("UTC"))
        self.assertTrue(is_valid_identifier("utc"))

    def test_format_offset_renders_sign_and_minutes(self):
        self.assertEqual(format_offset(0), "+00:00")
        self.assertEqual(format_offset(540), "+09:00")
        self.assertEqual(format_offset(-330), "-05:30")

    def test_plausibility_flags_an_impossible_regional_offset(self):
        plausible, _reason = plausibility("Europe/Berlin", 60)
        self.assertTrue(plausible)

        implausible, reason = plausibility("Europe/Berlin", 540)
        self.assertFalse(implausible)
        self.assertIn("Europe", reason)


class LocaleBehaviour(unittest.TestCase):

    def test_canonicalises_case(self):
        self.assertEqual(normalise_language_tag("en-us"), "en-US")
        self.assertEqual(normalise_language_tag("EN-GB"), "en-GB")
        self.assertEqual(normalise_language_tag("zh-hant-tw"), "zh-Hant-TW")
        self.assertEqual(normalise_language_tag("de_DE"), "de-DE")

    def test_rejects_malformed_tags(self):
        for tag in ("", "e", "english language", "en-US-x", "-en", 42):
            with self.assertRaises(Exception):
                normalise_language_tag(tag)

    def test_accept_language_header_shape(self):
        header = build_accept_language(["en-US", "de-DE", "fr-FR"])
        self.assertEqual(header, "en-US,de-DE;q=0.9,fr-FR;q=0.8")

    def test_accept_language_deduplicates(self):
        self.assertEqual(build_accept_language(["en-US", "en-US", "en-us"]), "en-US")

    def test_accept_language_never_reaches_zero_quality(self):
        import re

        header = build_accept_language(["en", "de", "fr", "es", "it", "pt", "nl", "sv", "pl", "da", "fi", "no"])
        qualities = [float(value) for value in re.findall(r";q=([0-9.]+)", header)]
        self.assertTrue(qualities)
        self.assertTrue(all(quality > 0 for quality in qualities))
        self.assertLessEqual(len(header.split(",")), 10)

    def test_five_surfaces_are_reported_separately(self):
        engine = LocaleEngine("en-US")
        resolution = engine.resolve("en-GB", ["en-GB", "de-DE"], "profile")
        self.assertEqual(resolution.browser_locale, "en-GB")
        self.assertEqual(resolution.system_locale, "en-US")
        self.assertEqual(resolution.js_locale, "en-GB")
        self.assertEqual(resolution.language_pref, ["en-GB", "de-DE"])
        self.assertTrue(resolution.http_language.startswith("en-GB"))

    def test_system_mode_does_not_invent_a_locale(self):
        resolution = LocaleEngine("de-DE").resolve(None, None, "system")
        self.assertEqual(resolution.browser_locale, "de-DE")
        self.assertEqual(resolution.source, "host")

    def test_configured_locale_leads_the_preference_list(self):
        resolution = LocaleEngine("en-US").resolve("ja-JP", ["en-US"], "profile")
        self.assertEqual(resolution.language_pref[0], "ja-JP")


class ResolverBehaviour(unittest.TestCase):

    def test_doh_requires_https(self):
        with self.assertRaises(InvalidResolverError):
            validate_doh_endpoint("http://dns.example/dns-query")

    def test_doh_accepts_a_well_formed_endpoint(self):
        self.assertEqual(validate_doh_endpoint("https://dns.example/dns-query"), "https://dns.example/dns-query")

    def test_ipv4_validation_rejects_out_of_range_octets(self):
        with self.assertRaises(InvalidResolverError):
            validate_ipv4("256.1.1.1")
        with self.assertRaises(InvalidResolverError):
            validate_ipv4("1.1.1")
        self.assertEqual(validate_ipv4("9.9.9.9"), "9.9.9.9")

    def test_hostname_validation(self):
        self.assertEqual(validate_hostname("DNS.Example"), "dns.example")
        with self.assertRaises(InvalidResolverError):
            validate_hostname("-bad.example")

    def test_system_mode_is_not_encrypted_and_is_not_modified(self):
        resolution = DnsEngine().resolve("system", None)
        self.assertFalse(resolution.encrypted)
        self.assertFalse(resolution.affects_operating_system)
        self.assertEqual(resolution.fallback, FALLBACK_REFUSE)

    def test_doh_plan_is_encrypted_and_certificate_validated(self):
        resolver = ResolverProfile("cf", "doh", endpoints=["https://cloudflare-dns.com/dns-query"])
        resolution = DnsEngine().resolve("doh", resolver)
        self.assertTrue(resolution.encrypted)
        self.assertTrue(resolution.certificate_validated)
        self.assertEqual(resolution.protocol, "DNS over HTTPS")

    def test_dot_plan_reports_host_and_port(self):
        resolver = ResolverProfile("q9", "dot", servers=["9.9.9.9"], port=853)
        resolution = DnsEngine().resolve("dot", resolver)
        self.assertTrue(resolution.encrypted)
        self.assertEqual(resolution.port, 853)
        self.assertEqual(resolution.servers, ["9.9.9.9"])

    def test_custom_mode_is_honestly_unencrypted(self):
        resolver = ResolverProfile("local", "custom", servers=["192.168.1.1"])
        resolution = DnsEngine().resolve("custom", resolver)
        self.assertFalse(resolution.encrypted)
        self.assertIn("unencrypted", resolution.detail)

    def test_encrypted_mode_without_resolver_is_refused(self):
        with self.assertRaises(InvalidResolverError):
            DnsEngine().resolve("doh", None)

    def test_explicit_fallback_is_reported_with_its_consequence(self):
        resolver = ResolverProfile("q9", "dot", servers=["9.9.9.9"], port=853, fallback="system")
        resolution = DnsEngine().resolve("dot", resolver)
        self.assertEqual(resolution.fallback, "system")
        self.assertIn("plaintext", resolution.fallback_protocol)

    def test_no_dns_plan_ever_claims_to_modify_the_operating_system(self):
        for mode, resolver in (
            ("system", None),
            ("custom", ResolverProfile("c", "custom", servers=["1.1.1.1"])),
            ("doh", ResolverProfile("d", "doh", endpoints=["https://dns.example/dns-query"])),
            ("dot", ResolverProfile("t", "dot", servers=["1.1.1.1"], port=853)),
        ):
            self.assertFalse(DnsEngine().resolve(mode, resolver).affects_operating_system)


class ProfileBehaviour(unittest.TestCase):

    def test_version_one_migrates_to_current(self):
        migrated, applied = migrate({"identifier": "old", "name": "Old", "latitude": 1.0, "longitude": 2.0})
        self.assertEqual(migrated["profile_version"], CURRENT_VERSION)
        self.assertTrue(any("geolocation_mode" in step for step in applied))
        self.assertTrue(any("dns_mode" in step for step in applied))

    def test_future_version_is_refused(self):
        with self.assertRaises(ProfileVersionError):
            migrate({"identifier": "future", "name": "Future", "profile_version": CURRENT_VERSION + 1})

    def test_checksum_detects_tampering(self):
        profile = GeoProfile(identifier="p", name="P", latitude=1.0, longitude=2.0)
        self.assertTrue(profile.verify_checksum())
        profile.latitude = 3.0
        self.assertFalse(profile.verify_checksum())

    def test_unknown_field_is_rejected_in_strict_mode(self):
        with self.assertRaises(ProfileSchemaError):
            GeoProfile.from_payload({"identifier": "p", "name": "P", "surprise": 1})

    def test_unknown_field_is_tolerated_when_not_strict(self):
        profile = GeoProfile.from_payload({"identifier": "p", "name": "P"}, strict=False)
        self.assertEqual(profile.identifier, "p")

    def test_reserved_identifier_is_rejected(self):
        with self.assertRaises(ProfileSchemaError):
            GeoProfile.from_payload({"identifier": "default", "name": "Shadow"})

    def test_virtual_mode_requires_a_latitude(self):
        with self.assertRaises(ProfileSchemaError):
            GeoProfile.from_payload({"identifier": "p", "name": "P", "geolocation_mode": "virtual"})

    def test_radius_without_area_mode_is_rejected(self):
        with self.assertRaises(ProfileSchemaError):
            GeoProfile.from_payload({"identifier": "p", "name": "P", "geolocation_mode": "automatic", "radius_m": 100})

    def test_encrypted_dns_mode_requires_a_resolver(self):
        with self.assertRaises(ProfileSchemaError):
            GeoProfile.from_payload({"identifier": "p", "name": "P", "dns_mode": "doh"})

    def test_import_rejects_a_bad_checksum(self):
        store = ProfileStore()
        payload = GeoProfile(identifier="p", name="P").to_payload()
        payload["latitude"] = 99.0
        with self.assertRaises(ProfileImportError):
            store.import_payload(payload)

    def test_import_accepts_a_valid_payload_and_reports_the_checksum(self):
        store = ProfileStore()
        imported = store.import_payload(GeoProfile(identifier="p", name="P").to_payload())
        self.assertEqual(imported.identifier, "p")
        self.assertTrue(imported.verify_checksum())

    def test_checksum_requirement_can_be_insisted_upon(self):
        store = ProfileStore()
        payload = GeoProfile(identifier="p", name="P").to_payload(include_checksum=False)
        with self.assertRaises(ProfileImportError):
            store.import_payload(payload, require_checksum=True)

    def test_export_round_trips(self):
        store = ProfileStore()
        original = GeoProfile(
            identifier="round",
            name="Round",
            geolocation_mode="virtual",
            latitude=1.0,
            longitude=2.0,
            radius_m=50.0,
        )
        store.add(original)
        exported = store.export("round")
        restored = GeoProfile.from_payload(exported)
        self.assertEqual(restored.identifier, original.identifier)
        self.assertEqual(restored.latitude, original.latitude)
        self.assertEqual(restored.checksum, original.checksum)

    def test_checksum_is_stable_regardless_of_key_order(self):
        first = {"b": 2, "a": 1}
        second = {"a": 1, "b": 2}
        self.assertEqual(compute_checksum(first), compute_checksum(second))

    def test_shipped_profiles_are_valid(self):
        for profile in default_profiles():
            self.assertTrue(profile.verify_checksum(), profile.identifier)


class StorageBehaviour(unittest.TestCase):

    def setUp(self):
        import shutil
        import tempfile

        self.work = pathlib.Path(tempfile.mkdtemp(prefix="platform-test-storage-"))
        self.addCleanup(shutil.rmtree, self.work, True)

    def test_fresh_root_is_seeded_and_indexed(self):
        storage = PlatformStorage(self.work)
        store = ProfileStore()

        for profile in default_profiles():
            store.add(profile)

        written = storage.save_all([store.get(name) for name in store.identifiers()])

        self.assertEqual(written, len(store))
        self.assertTrue((self.work / "profiles" / "index.json").exists())

        index = json.loads((self.work / "profiles" / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(index["identifiers"]), sorted(store.identifiers()))

    def test_a_profile_survives_a_round_trip_through_disk(self):
        storage = PlatformStorage(self.work)
        original = GeoProfile(
            identifier="round-trip",
            name="Round trip",
            geolocation_mode="virtual",
            latitude=48.8566,
            longitude=2.3522,
            radius_m=1200.0,
            timezone="Europe/Paris",
        )
        storage.save_all([original])

        store = ProfileStore()
        result = load_into(store, storage)

        self.assertEqual(result.quarantined, [])
        restored = store.get("round-trip")
        self.assertIsNotNone(restored)
        self.assertEqual(restored.latitude, original.latitude)
        self.assertEqual(restored.checksum, original.checksum)
        self.assertTrue(restored.verify_checksum())

    def test_active_profile_survives_a_restart(self):
        first = PlatformStorage(self.work)
        first.save_settings(active_profile="berlin-wide")

        second = PlatformStorage(self.work)

        self.assertEqual(second.settings["active_profile"], "berlin-wide")

    def test_unparsable_file_is_quarantined_and_reported(self):
        storage = PlatformStorage(self.work)
        storage.save_all([GeoProfile(identifier="broken", name="Broken")])
        (self.work / "profiles" / "broken.json").write_text('{"identifier": "broken", "name": ', encoding="utf-8")

        store = ProfileStore()
        result = load_into(store, storage)

        self.assertEqual(len(result.quarantined), 1)
        self.assertEqual(result.quarantined[0]["identifier"], "broken")
        self.assertIn("could not be parsed", result.quarantined[0]["reason"])
        self.assertTrue(result.quarantined[0]["moved_to"].endswith(".corrupt"))
        self.assertIsNone(store.get("broken"))

    def test_invalid_payload_is_quarantined_rather_than_loaded(self):
        storage = PlatformStorage(self.work)
        (self.work / "profiles" / "invalid.json").write_text(
            json.dumps({"identifier": "invalid", "name": "Invalid", "profile_version": 99}),
            encoding="utf-8",
        )

        store = ProfileStore()
        result = load_into(store, storage)

        self.assertEqual(len(result.quarantined), 1)
        self.assertIn("newer than this build supports", result.quarantined[0]["reason"])
        self.assertTrue(result.quarantined[0]["moved_to"].endswith(".corrupt"))
        self.assertEqual(len(store), 0)

    def test_a_tampered_checksum_is_caught_on_load(self):
        storage = PlatformStorage(self.work)
        profile = GeoProfile(
            identifier="tampered",
            name="Tampered",
            geolocation_mode="virtual",
            latitude=1.0,
            longitude=2.0,
        )
        storage.save_profile(profile)

        payload = json.loads((self.work / "profiles" / "tampered.json").read_text(encoding="utf-8"))
        payload["latitude"] = 55.0
        (self.work / "profiles" / "tampered.json").write_text(json.dumps(payload), encoding="utf-8")

        store = ProfileStore()
        result = load_into(store, storage)

        self.assertEqual(len(result.quarantined), 1)
        self.assertIn("checksum", result.quarantined[0]["reason"])
        self.assertIn("expected sha256:", result.quarantined[0]["reason"])
        self.assertIsNone(store.get("tampered"))
        self.assertTrue(result.quarantined[0]["moved_to"].endswith(".corrupt"))

    def test_index_naming_a_missing_file_is_reported_not_fatal(self):
        storage = PlatformStorage(self.work)
        atomic_write(
            self.work / "profiles" / "index.json",
            serialise({"layout_version": 1, "identifiers": ["ghost"]}),
        )

        store = ProfileStore()
        result = load_into(store, storage)

        self.assertIn("ghost", result.missing)
        self.assertEqual(len(store), 0)

    def test_path_building_refuses_to_leave_the_root(self):
        storage = PlatformStorage(self.work)

        for identifier in ("../escape", "..", "a/b", "with space", "", ".hidden"):
            with self.assertRaises(StorageError):
                storage._profile_path(identifier)

    def test_path_building_accepts_a_valid_identifier(self):
        storage = PlatformStorage(self.work)
        path = storage._profile_path("berlin-wide")

        self.assertTrue(str(path).startswith(str(storage.profiles_directory.resolve())))
        self.assertEqual(path.name, "berlin-wide.json")

    def test_unknown_setting_is_refused(self):
        storage = PlatformStorage(self.work)

        with self.assertRaises(StorageError):
            storage.save_settings(invented_preference=True)

    def test_settings_merge_nested_sections(self):
        storage = PlatformStorage(self.work)
        storage.save_settings(interface={"last_host": "example.com"})
        storage.save_settings(interface={"last_tab": "dns"})

        reloaded = PlatformStorage(self.work)

        self.assertEqual(reloaded.settings["interface"]["last_host"], "example.com")
        self.assertEqual(reloaded.settings["interface"]["last_tab"], "dns")

    def test_corrupt_settings_fall_back_to_defaults(self):
        storage = PlatformStorage(self.work)
        (self.work / "settings" / "settings.json").write_text("{not json", encoding="utf-8")

        reloaded = PlatformStorage(self.work)

        self.assertEqual(reloaded.settings["active_profile"], "default-environment")

    def test_atomic_write_leaves_no_temporary_file_behind(self):
        storage = PlatformStorage(self.work)
        target = self.work / "profiles" / "atomic.json"
        atomic_write(target, b'{"identifier": "atomic"}\n')

        leftovers = [path.name for path in (self.work / "profiles").iterdir() if path.name.startswith(".atomic")]
        self.assertEqual(leftovers, [])
        self.assertEqual(json.loads(target.read_text(encoding="utf-8"))["identifier"], "atomic")

    def test_diagnostic_export_is_written_and_pruned(self):
        storage = PlatformStorage(self.work)

        for index in range(5):
            storage.write_diagnostic({"index": index}, f"redacted-{index}")

        self.assertEqual(len(storage.list_diagnostics()), 5)
        removed = storage.prune_diagnostics(keep=2)
        self.assertEqual(removed, 3)
        self.assertEqual(len(storage.list_diagnostics()), 2)

    def test_storage_reports_when_it_cannot_persist(self):
        storage = PlatformStorage(self.work, writable=False)

        self.assertFalse(storage.persistent)
        self.assertEqual(storage.save_all([GeoProfile(identifier="x", name="X")]), 0)
        self.assertTrue(storage.notes)
        self.assertIn("memory", storage.notes[0])

    def test_summary_reports_the_layout(self):
        storage = PlatformStorage(self.work)
        storage.save_all([GeoProfile(identifier="one", name="One")])
        summary = storage.summary()

        self.assertTrue(summary["persistent"])
        self.assertEqual(summary["layout_version"], 1)
        self.assertEqual(summary["profiles_on_disk"], 1)


class PolicyPrecedence(unittest.TestCase):

    def test_origin_beats_subdomain_beats_domain(self):
        policies = [
            SitePolicy(pattern="example.com", scope="domain", timezone="UTC"),
            SitePolicy(pattern="api.example.com", scope="subdomain", locale="en-GB"),
            SitePolicy(pattern="api.example.com", scope="origin", profile="tokyo-precise"),
        ]
        winner, overshadowed = resolve_policy(policies, "api.example.com")
        self.assertEqual(winner.scope, "origin")
        self.assertEqual(len(overshadowed), 2)

    def test_no_match_returns_nothing(self):
        winner, overshadowed = resolve_policy(DEFAULT_POLICIES, "unrelated.test")
        self.assertIsNone(winner)
        self.assertEqual(overshadowed, [])

    def test_subdomain_scope_covers_children(self):
        policy = SitePolicy(pattern="example.com", scope="subdomain")
        self.assertTrue(policy.matches("example.com"))
        self.assertTrue(policy.matches("a.example.com"))
        self.assertFalse(policy.matches("notexample.com"))

    def test_origin_scope_is_exact(self):
        policy = SitePolicy(pattern="example.com", scope="origin")
        self.assertTrue(policy.matches("example.com"))
        self.assertFalse(policy.matches("a.example.com"))

    def test_unknown_scope_is_refused(self):
        with self.assertRaises(Exception):
            SitePolicy(pattern="example.com", scope="galaxy").matches("example.com")


class PipelineBehaviour(unittest.TestCase):

    def test_every_declared_stage_runs(self):
        snapshot = build_pipeline(detector=test_detector).run(
            GeoProfile(
                identifier="full",
                name="Full",
                geolocation_mode="virtual",
                latitude=BERLIN[0],
                longitude=BERLIN[1],
                radius_m=500.0,
                dns_mode="doh",
                dns_resolver="cloudflare-doh",
            )
        )
        names = [stage["name"] for stage in snapshot["stages"]]
        self.assertEqual(
            names,
            [
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
            ],
        )

    def test_virtual_profile_reports_manual_state(self):
        profile = GeoProfile(identifier="v", name="V", geolocation_mode="virtual", latitude=1.0, longitude=2.0)
        self.assertEqual(build_pipeline().run(profile)["state"], STATE_MANUAL)

    def test_hybrid_without_a_detector_fails_clearly(self):
        profile = GeoProfile(identifier="h", name="H", geolocation_mode="hybrid", latitude=1.0, longitude=2.0)
        snapshot = build_pipeline(detector=None).run(profile)
        self.assertEqual(snapshot["state"], STATE_ERROR)
        self.assertEqual(snapshot["failed_stage"], "geo_resolution")

    def test_hybrid_uses_the_detector_when_one_exists(self):
        def detector(_context):
            return {"latitude": 48.8566, "longitude": 2.3522, "radius_m": 1000.0, "country": "FR", "confidence": "low", "reason": "test"}

        profile = GeoProfile(identifier="h", name="H", geolocation_mode="hybrid", latitude=48.8566, longitude=2.3522, radius_m=1000.0)
        snapshot = build_pipeline(detector=detector).run(profile)
        self.assertEqual(snapshot["state"], "HYBRID")
        self.assertIsNotNone(snapshot["geo"])

    def test_policy_overrides_the_profile_for_a_matching_host(self):
        snapshot = build_pipeline().run(
            GeoProfile(identifier="any", name="Any", geolocation_mode="automatic", timezone="UTC", timezone_mode="profile"),
            host="internal.example",
        )
        self.assertIsNotNone(snapshot["policy"])
        self.assertEqual(snapshot["policy"]["pattern"], "internal.example")

    def test_no_policy_for_an_unmatched_host(self):
        snapshot = build_pipeline().run(GeoProfile(identifier="any", name="Any", geolocation_mode="automatic"), host="unrelated.test")
        self.assertIsNone(snapshot["policy"])

    def test_geo_failure_stops_the_pipeline_before_later_stages(self):
        profile = GeoProfile(identifier="off", name="Off", geolocation_mode="disabled")
        snapshot = build_pipeline().run(profile)
        names = [stage["name"] for stage in snapshot["stages"]]
        self.assertNotIn("dns_resolution", names)
        self.assertNotIn("browser_handoff", names)

    def test_privacy_stage_carries_the_webrtc_caveat(self):
        profile = GeoProfile(identifier="w", name="W", geolocation_mode="virtual", latitude=1.0, longitude=2.0, webrtc_policy="privacy_enhanced")
        snapshot = build_pipeline().run(profile)
        stage = [item for item in snapshot["stages"] if item["name"] == "privacy_policy"][0]
        self.assertIn("anonymous", stage["output"]["webrtc"]["caveat"])

    def test_handoff_contains_the_resolved_surfaces(self):
        profile = GeoProfile(identifier="x", name="X", geolocation_mode="virtual", latitude=1.0, longitude=2.0)
        snapshot = build_pipeline().run(profile)
        stage = [item for item in snapshot["stages"] if item["name"] == "browser_handoff"][0]
        for key in ("geo", "timezone", "locale", "webrtc", "profile"):
            self.assertIn(key, stage["output"])


class DiagnosticsBehaviour(unittest.TestCase):

    def test_ipv4_masking_keeps_only_the_network(self):
        self.assertEqual(redact_ipv4("192.168.1.77"), "192.168.x.x")
        self.assertEqual(redact_ipv4("address 10.0.0.1 and 8.8.4.4"), "address 10.0.x.x and 8.8.x.x")

    def test_credential_shaped_values_never_survive_redaction(self):
        payload = {"api_key": "abc", "nested": {"session_token": "xyz"}, "safe": "value"}

        cleaned = redact_snapshot(payload, REDACTION_REDACTED)
        self.assertEqual(cleaned["api_key"], "[removed]")
        self.assertEqual(cleaned["nested"]["session_token"], "[removed]")
        self.assertEqual(cleaned["safe"], "value")
        self.assertNotIn("abc", str(cleaned))
        self.assertNotIn("xyz", str(cleaned))

        minimal = redact_snapshot(payload, REDACTION_MINIMAL)
        self.assertNotIn("abc", str(minimal))
        self.assertNotIn("xyz", str(minimal))

    def test_minimal_level_keeps_only_summary_keys(self):
        cleaned = redact_snapshot({"state": "MANUAL", "geo": {"latitude": 1.0}, "generated_at": "now", "profile": "p"}, REDACTION_MINIMAL)
        self.assertIn("state", cleaned)
        self.assertNotIn("geo", cleaned)

    def test_redacted_level_rounds_coordinates_and_keeps_them(self):
        cleaned = redact_snapshot({"geo": {"latitude": 52.52001234, "longitude": 13.40504321}}, REDACTION_REDACTED)
        self.assertEqual(cleaned["geo"]["latitude"], 52.52)
        self.assertEqual(cleaned["geo"]["longitude"], 13.41)

    def test_analysis_reports_a_timezone_country_mismatch(self):
        snapshot = {
            "geo": {"latitude": 1.0, "longitude": 2.0},
            "timezone": {"identifier": "Asia/Tokyo", "offset_minutes": 540},
            "locale": {"browser_locale": "en-US"},
            "dns": {"mode": "doh", "encrypted": True, "certificate_validated": True, "fallback": "refuse"},
            "profile": {"country": "DE"},
        }
        result = analyse(snapshot)
        identifiers = [finding["identifier"] for finding in result["findings"]]
        self.assertIn("timezone.country_mismatch", identifiers)

    def test_analysis_reports_a_plaintext_fallback(self):
        snapshot = {
            "geo": {"latitude": 1.0, "longitude": 2.0},
            "timezone": {"identifier": "UTC"},
            "locale": {"browser_locale": "en-US"},
            "dns": {"mode": "dot", "encrypted": True, "certificate_validated": True, "fallback": "system"},
            "profile": {"country": "US"},
        }
        identifiers = [finding["identifier"] for finding in analyse(snapshot)["findings"]]
        self.assertIn("dns.plaintext_fallback", identifiers)

    def test_analysis_states_what_it_did_not_examine(self):
        result = analyse({"geo": {"latitude": 1.0, "longitude": 2.0}, "timezone": {"identifier": "UTC"}, "locale": {"browser_locale": "en-US"}, "dns": {}, "profile": {"country": "US"}})
        for surface in ("canvas", "webgl", "fonts"):
            self.assertIn(surface, result["surfaces_not_examined"])
        self.assertIn("not fingerprint protection", result["caveat"])

    def test_report_defaults_to_redacted(self):
        snapshot = build_pipeline().run(GeoProfile(identifier="r", name="R", geolocation_mode="automatic"))
        report = build_report(snapshot)
        self.assertEqual(report["redaction_level"], "redacted")

    def test_report_is_json_serialisable_at_every_level(self):
        import json

        snapshot = build_pipeline().run(GeoProfile(identifier="r", name="R", geolocation_mode="automatic"))

        for level in ("full", "redacted", "minimal"):
            json.dumps(build_report(snapshot, level=level))

    def test_unknown_redaction_level_is_refused(self):
        with self.assertRaises(ValueError):
            build_report({}, level="secret")


class HostDetectorBehaviour(unittest.TestCase):

    def test_detection_admits_weak_precision(self):
        from core.host import HostDetector

        detector = HostDetector({"timezone": "Europe/Berlin", "timezone_source": "test", "locale": "en-US", "locale_source": "test", "network": {}})
        result = detector({})
        self.assertEqual(result["country"], "DE")
        self.assertEqual(result["confidence"], "low")
        self.assertGreaterEqual(result["radius_m"], 100000)
        self.assertIn("not a position", result["reason"])

    def test_unknown_timezone_returns_no_invented_centre(self):
        from core.host import HostDetector

        detector = HostDetector({"timezone": "Etc/UTC", "timezone_source": "test", "locale": "en-US", "locale_source": "test", "network": {}})
        result = detector({})
        self.assertIsNone(result["country"])
        self.assertEqual(result["confidence"], "low")


if __name__ == "__main__":
    unittest.main(verbosity=2)
