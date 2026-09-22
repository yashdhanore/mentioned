from __future__ import annotations

import enum


class SourceFailureReason(enum.StrEnum):
    DOWNLOAD_FAILED = "download_failed"
    NO_MEDIA = "no_media"
    EXTRACTION_FAILED = "extraction_failed"
    TOO_MANY_ATTEMPTS = "too_many_attempts"
    UNEXPECTED_ERROR = "unexpected_error"


# The mobile app does not currently render error_message (it shows a fixed
# "Could not find mentions" state for any failed source), but the API returns
# this text to every user who saved the URL, so it must never carry raw
# exception detail. Keep the raw exception in server-side logs only.
_SAFE_ERROR_MESSAGES: dict[SourceFailureReason, str] = {
    SourceFailureReason.DOWNLOAD_FAILED: "Download failed. The original post's media could not "
    "be downloaded.",
    SourceFailureReason.NO_MEDIA: "This post has no downloadable photo or video.",
    SourceFailureReason.EXTRACTION_FAILED: "Extraction failed. This post's media could not be "
    "analyzed.",
    SourceFailureReason.TOO_MANY_ATTEMPTS: "This post could not be processed after repeated "
    "attempts.",
    SourceFailureReason.UNEXPECTED_ERROR: "Something went wrong while processing this post.",
}


def safe_source_error_message(reason: SourceFailureReason) -> str:
    return _SAFE_ERROR_MESSAGES[reason]
