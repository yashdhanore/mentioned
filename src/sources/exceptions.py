from __future__ import annotations

from src.errors import AppError


class InvalidSourceUrl(AppError):
    status_code = 400
    error_code = "invalid_source_url"
    message = "Invalid source URL"


class SavedSourceNotFound(AppError):
    status_code = 404
    error_code = "saved_source_not_found"
    message = "Saved source not found"


class RateLimited(AppError):
    status_code = 429
    error_code = "rate_limited"
    message = "Too many requests"


class QuotaExceeded(AppError):
    status_code = 429
    error_code = "quota_exceeded"
    message = "Quota exceeded"
