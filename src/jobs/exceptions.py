from __future__ import annotations


class JobError(Exception):
    status_code: int = 400
    error_code: str = "job_error"
    message: str = "An error occurred"


class JobNotFound(JobError):
    status_code = 404
    error_code = "job_not_found"
    message = "Job not found"


class RateLimited(JobError):
    status_code = 429
    error_code = "rate_limited"
    message = "Too many requests"


class QuotaExceeded(JobError):
    status_code = 429
    error_code = "quota_exceeded"
    message = "Quota exceeded"
