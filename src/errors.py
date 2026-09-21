from __future__ import annotations


class AppError(Exception):
    status_code: int = 400
    error_code: str = "app_error"
    message: str = "An error occurred"
