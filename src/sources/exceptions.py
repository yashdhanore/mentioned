from __future__ import annotations


class SourceError(Exception):
    status_code: int = 400
    error_code: str = "source_error"
    message: str = "An error occurred"


class InvalidSourceUrl(SourceError):
    status_code = 400
    error_code = "invalid_source_url"
    message = "Invalid source URL"


class SavedSourceNotFound(SourceError):
    status_code = 404
    error_code = "saved_source_not_found"
    message = "Saved source not found"
