"""Storage: keeping profiles and settings on disk without losing them.

The roadmap specifies a layout (section 39) and a recovery requirement
(section 52). Both shape this module.

Layout:

    <root>/
        profiles/
            index.json                 identifiers, and when the set last changed
            <identifier>.json          one profile payload with its checksum
        settings/
            settings.json              active profile and interface preferences
        diagnostics/
            <stamp>-<level>.json       exported reports

Three properties matter more than the layout.

A write is atomic. A profile is serialised to a temporary file in the same
directory and then renamed over the target. Renaming within a directory is
atomic on every platform this runs on, so a process that dies mid-write leaves
the previous file intact rather than a truncated one.

A corrupt file is quarantined, not ignored. When a profile fails to parse or
fails its checksum, it is moved aside with a timestamped name and reported in
the load result. Silently dropping it would mean the user's configuration
disappeared with no way to find out why; crashing would mean a single bad file
makes the application unusable.

The root never escapes. An identifier that passes validation cannot contain a
separator, and the resolved path is checked against the root anyway. Validation
in one place is a convention; validation at the boundary that builds the path is
a guarantee.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone as dt_timezone
from typing import Optional

from .errors import ProfileImportError, ProfileSchemaError, StorageError
from .profiles import CURRENT_VERSION, GeoProfile, validate_identifier

LAYOUT_VERSION = 1

PROFILES_DIRECTORY = "profiles"
SETTINGS_DIRECTORY = "settings"
DIAGNOSTICS_DIRECTORY = "diagnostics"

INDEX_FILE = "index.json"
SETTINGS_FILE = "settings.json"

DEFAULT_SETTINGS = {
    "layout_version": LAYOUT_VERSION,
    "active_profile": "default-environment",
    "redaction_level": "redacted",
    "session_id": "",
    "interface": {
        "last_host": "",
        "last_tab": "overview",
    },
}

SAFE_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")

MAX_PROFILE_BYTES = 65536
MAX_INDEX_BYTES = 262144


def stamp() -> str:
    return datetime.now(dt_timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def serialise(payload: dict, indent: int = 2) -> bytes:
    return (json.dumps(payload, indent=indent, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def atomic_write(path: pathlib.Path, data: bytes) -> None:
    """Write data to path so that a crash leaves either the old file or the new one.

    The temporary file is created in the destination directory, because a rename
    across filesystems is a copy and loses the atomicity this function exists to
    provide.
    """
    directory = path.parent
    handle, temporary = tempfile.mkstemp(prefix="." + path.name + ".", dir=str(directory))

    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())

        os.replace(temporary, path)
    except OSError:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


@dataclass
class LoadResult:
    """What a load found: usable payloads, and the files it could not use.

    `payloads` holds raw parsed JSON rather than profiles, because validation
    belongs in one place. This module reads bytes and moves unusable files aside;
    `ProfileStore.import_payload` decides what a valid profile is. Duplicating
    that decision here is how the two would eventually disagree.
    """

    payloads: list = field(default_factory=list)
    profiles: list = field(default_factory=list)
    quarantined: list = field(default_factory=list)
    missing: list = field(default_factory=list)
    notes: list = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "loaded": [profile.identifier for profile in self.profiles],
            "quarantined": list(self.quarantined),
            "missing": list(self.missing),
            "notes": list(self.notes),
        }


class PlatformStorage:
    """A store backed by a directory, or by nothing if the directory is unusable."""

    def __init__(self, root, writable: Optional[bool] = None):
        self.root = pathlib.Path(root).expanduser()
        self.profiles_directory = self.root / PROFILES_DIRECTORY
        self.settings_directory = self.root / SETTINGS_DIRECTORY
        self.diagnostics_directory = self.root / DIAGNOSTICS_DIRECTORY
        self.settings = dict(DEFAULT_SETTINGS)
        self.notes = []
        self.persistent = True

        if writable is False:
            self.persistent = False
            self.notes.append("storage was disabled by the caller, so this session keeps everything in memory")
            return

        try:
            self.profiles_directory.mkdir(parents=True, exist_ok=True)
            self.settings_directory.mkdir(parents=True, exist_ok=True)
            self.diagnostics_directory.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            self.persistent = False
            self.notes.append(f"storage directory is not writable ({error}), so this session keeps everything in memory")
            return

        probe = self.profiles_directory / ".write-probe"

        try:
            atomic_write(probe, b"probe\n")
            probe.unlink()
        except OSError as error:
            self.persistent = False
            self.notes.append(f"storage directory refused a write ({error}), so this session keeps everything in memory")
            return

        self.settings = self._read_settings()

    def _profile_path(self, identifier: str) -> pathlib.Path:
        """Build a profile path, refusing anything that could leave the root.

        `validate_identifier` already excludes separators, so this is the second
        check rather than the only one. It exists because this function is the
        boundary where a string becomes a filesystem path, and that boundary
        should not depend on a validator somewhere else remaining correct.
        """
        if not isinstance(identifier, str) or not SAFE_IDENTIFIER.match(identifier):
            raise StorageError(
                f"refusing to build a path for identifier {identifier!r}",
                "an identifier must be lowercase alphanumeric with dots, dashes or underscores",
            )

        candidate = (self.profiles_directory / f"{identifier}.json").resolve()

        try:
            candidate.relative_to(self.profiles_directory.resolve())
        except ValueError as error:
            raise StorageError(
                f"identifier {identifier!r} resolved outside the profiles directory",
                f"resolved to {candidate}",
            ) from error

        return candidate

    def load(self) -> LoadResult:
        result = LoadResult(notes=list(self.notes))

        if not self.persistent:
            return result

        index = self._read_index()

        if index is None:
            result.notes.append("no index was readable, so profiles are discovered by scanning the directory")
            names = sorted(path.stem for path in self.profiles_directory.glob("*.json") if path.name != INDEX_FILE)
        else:
            names = index.get("identifiers", [])

            for name in names:
                if not self._profile_path_safe(name):
                    result.notes.append(f"index contains an unusable identifier {name!r}, which was skipped")
                    result.missing.append(name)

        seen = set()

        for name in names:
            if not self._profile_path_safe(name) or name in seen:
                continue

            seen.add(name)
            path = self._profile_path(name)

            if not path.exists():
                result.missing.append(name)
                result.notes.append(f"index lists {name!r} but no file exists for it")
                continue

            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
                quarantined = self._quarantine(path, "unreadable")
                result.quarantined.append({"identifier": name, "reason": f"could not be parsed: {error}", "moved_to": quarantined})
                continue

            if not isinstance(payload, dict):
                quarantined = self._quarantine(path, "invalid")
                result.quarantined.append({"identifier": name, "reason": "the file does not contain a JSON object", "moved_to": quarantined})
                continue

            result.payloads.append((name, path, payload))

        result.notes.append(f"settings loaded, active profile is {self.settings.get('active_profile')!r}")

        return result

    def quarantine_payload(self, name: str, reason: str) -> str:
        """Move an unusable profile file aside, addressed by identifier."""
        try:
            return self._quarantine(self._profile_path(name), reason)
        except StorageError:
            return ""

    def _profile_path_safe(self, identifier) -> bool:
        return isinstance(identifier, str) and bool(SAFE_IDENTIFIER.match(identifier))

    def _quarantine(self, path: pathlib.Path, reason: str) -> str:
        """Move an unusable file aside so a human can inspect it later."""
        target = path.with_name(f"{path.stem}.{reason}.{stamp()}.corrupt")

        try:
            os.replace(path, target)
            return target.name
        except OSError:
            return ""

    def _read_index(self) -> Optional[dict]:
        path = self.profiles_directory / INDEX_FILE

        if not path.exists():
            return None

        try:
            if path.stat().st_size > MAX_INDEX_BYTES:
                return None
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None

        if not isinstance(payload, dict) or not isinstance(payload.get("identifiers"), list):
            return None

        return payload

    def _write_index(self, identifiers: list) -> None:
        if not self.persistent:
            return

        payload = {
            "layout_version": LAYOUT_VERSION,
            "profile_version": CURRENT_VERSION,
            "updated_at": stamp(),
            "identifiers": sorted(identifiers),
        }

        atomic_write(self.profiles_directory / INDEX_FILE, serialise(payload))

    def _read_settings(self) -> dict:
        settings = json.loads(json.dumps(DEFAULT_SETTINGS))
        path = self.settings_directory / SETTINGS_FILE

        if not path.exists():
            return settings

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return settings

        if not isinstance(payload, dict):
            return settings

        for key, default in DEFAULT_SETTINGS.items():
            value = payload.get(key, default)

            if isinstance(default, dict) and isinstance(value, dict):
                merged = dict(default)
                merged.update(value)
                settings[key] = merged
            else:
                settings[key] = value

        return settings

    def save_settings(self, **changes) -> dict:
        for key, value in changes.items():
            if key not in DEFAULT_SETTINGS:
                raise StorageError(f"unknown setting {key!r}", "settings are a closed set")

            if isinstance(DEFAULT_SETTINGS[key], dict) and isinstance(value, dict):
                merged = dict(self.settings.get(key, {}))
                merged.update(value)
                self.settings[key] = merged
            else:
                self.settings[key] = value

        self.settings["layout_version"] = LAYOUT_VERSION

        if self.persistent:
            atomic_write(self.settings_directory / SETTINGS_FILE, serialise(self.settings))

        return dict(self.settings)

    def save_profile(self, profile: GeoProfile) -> pathlib.Path:
        if not self.persistent:
            return pathlib.Path("")

        identifier = validate_identifier(profile.identifier)
        path = self._profile_path(identifier)
        atomic_write(path, serialise(profile.to_payload()))

        return path

    def delete_profile(self, identifier: str) -> bool:
        if not self.persistent:
            return False

        path = self._profile_path(identifier)

        if not path.exists():
            return False

        try:
            path.unlink()
            return True
        except OSError as error:
            raise StorageError(f"could not delete {identifier!r}", str(error)) from error

    def save_all(self, profiles: list) -> int:
        if not self.persistent:
            return 0

        written = 0

        for profile in profiles:
            self.save_profile(profile)
            written += 1

        self._write_index([profile.identifier for profile in profiles])

        return written

    def write_diagnostic(self, payload: dict, level: str) -> pathlib.Path:
        """Write a report under a name that cannot collide with an earlier one.

        The timestamp has one second of resolution, so two exports inside the
        same second would otherwise overwrite each other and the user would lose
        the report they had just asked for.
        """
        if not self.persistent:
            return pathlib.Path("")

        label = re.sub(r"[^a-z0-9]+", "-", str(level).lower()).strip("-") or "report"
        path = self.diagnostics_directory / f"{stamp()}-{label}.json"
        suffix = 1

        while path.exists():
            path = self.diagnostics_directory / f"{stamp()}-{label}-{suffix}.json"
            suffix += 1

        atomic_write(path, serialise(payload))

        return path

    def list_diagnostics(self) -> list:
        if not self.persistent:
            return []

        entries = []

        for path in sorted(self.diagnostics_directory.glob("*.json"), reverse=True):
            try:
                entries.append({"name": path.name, "bytes": path.stat().st_size})
            except OSError:
                continue

        return entries

    def prune_diagnostics(self, keep: int = 20) -> int:
        if not self.persistent:
            return 0

        files = sorted(self.diagnostics_directory.glob("*.json"), reverse=True)
        removed = 0

        for path in files[keep:]:
            try:
                path.unlink()
                removed += 1
            except OSError:
                continue

        return removed

    def summary(self) -> dict:
        return {
            "root": str(self.root),
            "persistent": self.persistent,
            "layout_version": LAYOUT_VERSION,
            "profiles_on_disk": len(list(self.profiles_directory.glob("*.json"))) - (1 if (self.profiles_directory / INDEX_FILE).exists() else 0),
            "diagnostics_on_disk": len(self.list_diagnostics()),
            "notes": list(self.notes),
        }


def load_into(store, storage: PlatformStorage) -> LoadResult:
    """Fill a ProfileStore from disk, importing only what survives validation.

    Every payload goes through `ProfileStore.import_payload`, which is the same
    path an untrusted paste from the interface takes. That is deliberate: a
    checksum comparison written a second time here would be a second chance to
    get it wrong, and the first version of this module did get it wrong, because
    `from_payload` reseals a profile and so hid a tampered file from a check
    performed afterwards.
    """
    result = storage.load()

    for name, _path, payload in result.payloads:
        try:
            profile = store.import_payload(payload, strict=True)
        except Exception as error:
            message = getattr(error, "message", "") or str(error)
            detail = getattr(error, "detail", "")
            reason = f"{message}: {detail}" if detail else message
            moved = storage.quarantine_payload(name, "invalid")
            result.quarantined.append({"identifier": name, "reason": reason, "moved_to": moved})
            continue

        if profile.checksum != payload.get("checksum"):
            storage.save_profile(profile)
            result.notes.append(f"{name!r} carried no checksum and was resealed on load")

        result.profiles.append(profile)

    return result
