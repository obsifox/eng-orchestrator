"""Structured error types shared by the environment core.

Every engine raises a subclass of EnvironmentError so callers can distinguish a
configuration mistake from an unavailable signal. The pipeline in
core/environment.py turns these into a stage failure with a stated reason rather
than a partially applied environment.
"""

from __future__ import annotations


class EnvironmentError(Exception):
    """Base class for every environment failure."""

    stage = "environment"

    def __init__(self, message: str, detail: str = ""):
        super().__init__(message)
        self.message = message
        self.detail = detail

    def as_dict(self) -> dict:
        return {"stage": self.stage, "message": self.message, "detail": self.detail}


class InvalidCoordinateError(EnvironmentError):
    """A latitude or longitude outside its valid range."""

    stage = "geo"


class InvalidRadiusError(EnvironmentError):
    """A radius that is negative, zero where a disc is required, or absurd."""

    stage = "geo"


class GeoProviderError(EnvironmentError):
    """A geo provider could not produce a location."""

    stage = "geo"


class UnknownTimezoneError(EnvironmentError):
    """A timezone identifier that the local tz database does not contain."""

    stage = "timezone"


class InvalidLocaleError(EnvironmentError):
    """A locale or language tag that is not well formed."""

    stage = "locale"


class InvalidResolverError(EnvironmentError):
    """A DNS resolver configuration that cannot be used as described."""

    stage = "dns"


class ProfileError(EnvironmentError):
    """Base class for profile failures."""

    stage = "profile"


class ProfileSchemaError(ProfileError):
    """A profile that violates its schema."""


class ProfileVersionError(ProfileError):
    """A profile version with no migration path to the current version."""


class ProfileImportError(ProfileError):
    """An imported profile that failed validation before activation."""


class StorageError(EnvironmentError):
    """A storage operation that could not be completed safely."""

    stage = "storage"


class PolicyError(EnvironmentError):
    """A per-site policy that cannot be parsed or applied."""

    stage = "policy"


class PipelineError(EnvironmentError):
    """A pipeline stage failure that prevents a coherent environment."""

    stage = "pipeline"
