from __future__ import annotations


class MentionError(Exception):
    status_code: int = 400
    error_code: str = "mention_error"
    message: str = "An error occurred"


class MentionNotFound(MentionError):
    status_code = 404
    error_code = "mention_not_found"
    message = "Mention not found"
