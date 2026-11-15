"""Domain errors mapped to HTTP responses in ``app.main``."""

from __future__ import annotations


class ApiError(Exception):
    status_code = 500
    code = "internal_error"

    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint


class EventNotFound(ApiError):
    status_code = 404
    code = "event_not_found"


class InspectionNotFound(ApiError):
    status_code = 404
    code = "inspection_not_found"


class FixtureNotBuilt(ApiError):
    status_code = 409
    code = "fixture_not_built"


class FixtureInvalid(ApiError):
    status_code = 500
    code = "fixture_invalid"


class ConfigurationInvalid(ApiError):
    status_code = 500
    code = "configuration_invalid"
