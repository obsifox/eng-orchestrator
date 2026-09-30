# Browser Platform: Environment Core

A working implementation of the environment resolution layer described by the browser platform roadmap: geographic location, timezone, locale, browser-scoped DNS, profiles, per-site policy, and consistency diagnostics, with a control center interface over the top.

This is not a browser. It is the part of the platform that decides what a browser should present, kept separate from the engine that would present it. The separation is deliberate: the resolution logic is testable without a browser engine, and the browser engine receives a descriptor rather than reading configuration from six places.

## Running it

```
python3 server.py --host 0.0.0.0 --port 8770
```

Then open the served origin. The interface and the API share one origin, so there is no second service and no cross-origin configuration.

No dependencies, no install step, no lockfile, no build. Python 3.9 or newer with a standard library is the entire requirement. The timezone engine uses the system tz database through `zoneinfo`.

## Tests

```
./run_tests.sh
```

Runs the unit suite and then the content policy over the application source. Both must pass. The suite currently reports 100 tests, and the policy reports 0 findings across 30 files.

The storage tests build their own temporary roots, so the suite never touches `data/` and leaves nothing behind.

```
python3 -m unittest discover -s tests -t . -v
```

## What it does

| Area | Behaviour |
| --- | --- |
| Location | Resolves a position from a configured area or a host source. A radius samples uniformly over the disc, reproducibly under a seed. |
| Timezone | Resolves a browser-scoped identifier, offset and daylight-saving state, validated against the local tz database. |
| Locale | Keeps five surfaces apart: browser locale, language preference, HTTP language, JavaScript locale, and system locale. |
| DNS | Produces a browser-scoped resolution plan for system, custom, DoH and DoT modes. Validates every endpoint and port. |
| Profiles | Versioned, checksummed, migration-aware, importable and exportable. An import is validated before it can be activated. |
| Per-site policy | Overrides the profile for a matching host with a deterministic precedence order. |
| Storage | Profiles, settings and diagnostic exports are written to disk. Imports, activations and deletions survive a restart. |
| Diagnostics | Reports where the resolved surfaces disagree, at one of three redaction levels. |

## What it deliberately does not do

These limits are properties of the design, not gaps to be filled later.

**It does not modify the operating system.** The DNS engine imports no networking library and holds no file handle. It produces a plan; it cannot write `/etc/resolv.conf` even by mistake. Every plan carries `affects_operating_system: false`, and a test asserts that for all four modes.

**It does not fall back silently.** When a configured environment cannot be resolved, the pipeline stops and reports which stage failed. It never substitutes a measured position for a configured one. The geolocation stage records `no fallback provider was consulted` in its notes on failure, and a test asserts that no physical source appears anywhere in a failed snapshot.

**It does not claim precision it lacks.** Automatic detection from host signals returns a country centroid with a country-sized radius and an explicit `low` confidence, because a timezone identifies a band of the globe and not a position within it.

**It does not claim anonymity.** Neither the diagnostics nor the interface suggests that a coherent environment protects a fingerprint. The consistency report names what it examined and lists what it did not, including canvas, WebGL, audio, fonts and screen metrics.

**It does not treat an imported profile as trusted.** A checksum proves a file is intact, not that it is safe. Every imported profile is schema-checked, range-checked and enum-checked before it can be activated, and a profile from a newer schema version is refused rather than interpreted.

## Layout

```
platform/
  server.py                 HTTP API and static interface on one origin
  policy.yaml               content policy the source satisfies
  run_tests.sh              tests, then policy
  core/
    errors.py               structured failures, one type per stage
    geo.py                  providers, radius sampling, distance
    timezone_engine.py      identifiers, offsets, daylight saving, plausibility
    locale_engine.py        language tags, Accept-Language, five surfaces
    dns_engine.py           resolution plans for system, custom, DoH, DoT
    profiles.py             schema, versioning, migration, checksums
    environment.py          the ten-stage pipeline and per-site policy
    diagnostics.py          consistency reporting and redaction
    host.py                 host signals and the honest detector
    catalog.py              offline sample data
    storage.py              atomic writes, quarantine, settings, index
  ui/                       interface, no build step
  data/                     runtime state, created on first start, not committed
  tests/test_platform.py    the suite
```

## Content policy

The source satisfies `policy.yaml`, which forbids slash comments, emoji, non-permitted writing systems and organisation branding. This is enforced by the scanner in the parent repository rather than by convention:

```
python3 scripts/policy_scan.py --config platform/policy.yaml --root platform
```

Writing comment-free JavaScript and Python is achievable through naming and documentation, and the constraint removes an entire category of drift between code and its stated behaviour. The policy file excludes itself from its own scope, because a policy necessarily names every string it prohibits.

## Design notes worth knowing

**Uniform over the disc, not over the radius.** Sampling a radius uniformly crowds points toward the centre, because a ring of radius `r` has circumference proportional to `r`. The engine samples `R * sqrt(u)`, which puts the mean at two thirds of the radius. A test asserts that mean against 1500 samples.

**Five locale surfaces.** `browser_locale`, `language_pref`, `http_language`, `js_locale` and `system_locale` are stored and reported separately. A page can observe several of them, and they do not have to agree.

**Precedence is total.** Origin beats subdomain beats domain, then longer patterns beat shorter ones at the same scope. There is no tie that the ordering cannot break.

**Provenance travels with every value.** Each resolved value carries a source and a confidence, so the interface can mark a configured decision as configured and a derived one as derived.

**Observation times are recorded.** Each pipeline stage reports its own duration and start time, which is what the interface turns into the stage list and what makes a slow stage visible.

**Writes are atomic.** A profile is serialised to a temporary file in the destination directory and renamed over the target. Renaming within a directory is atomic, so a process that dies mid-write leaves the previous file intact rather than a truncated one.

**A corrupt file is quarantined, not ignored.** When a profile fails to parse, or fails validation, or carries a checksum that does not match its contents, it is renamed with a reason and a timestamp and reported in the load result. The application still starts. Silently dropping the file would make a user's configuration vanish with no explanation, and refusing to start would let one bad file make the application unusable.

**Validation has exactly one path.** Files loaded from disk go through the same `ProfileStore.import_payload` that an untrusted paste from the interface goes through. The first version of the storage module checked checksums itself, after `from_payload` had already resealed the profile, so a tampered file loaded silently. Reusing one path removes the second chance to get it wrong.

**The storage root never escapes.** An identifier that passes validation cannot contain a separator, and the resolved path is checked against the root anyway. Validation in one place is a convention; validation at the boundary that turns a string into a path is a guarantee.
