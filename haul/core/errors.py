"""Custom exception hierarchy for HAUL.

Every error HAUL raises on purpose is a subclass of HaulError, so the
CLI layer can catch exactly one type and render a consistent, human
-readable message (spec §18) instead of leaking a raw traceback or a
library-specific exception like ``HTTPError: 403 Client Error``.
"""

from __future__ import annotations


class HaulError(Exception):
    """Base class for every error HAUL raises intentionally.

    Subclasses set a short ``reason`` and a list of ``suggestions``
    that :meth:`render` turns into the "Good" error format from the
    product spec. Callers may override the reason per-instance via
    ``detail`` when they have something more specific to say.
    """

    reason: str = "An unknown error occurred."
    suggestions: list[str] = []

    def __init__(self, detail: str | None = None, *, url: str | None = None):
        self.detail = detail
        self.url = url
        super().__init__(detail or self.reason)

    def render(self) -> str:
        lines = ["✗ Unable to complete the request.", "", "Reason:", self.detail or self.reason]
        if self.url:
            lines += ["", "URL:", self.url]
        if self.suggestions:
            lines += ["", "Try:"] + [f"- {s}" for s in self.suggestions]
        return "\n".join(lines)


class UnsupportedPlatform(HaulError):
    reason = "This platform is not yet supported by HAUL."
    suggestions = [
        "Run 'haul --help' to see supported platforms.",
        "Open an issue if you'd like this platform added.",
    ]


class InvalidURL(HaulError):
    reason = "The provided URL is not valid."
    suggestions = [
        "Double-check the URL was copied in full.",
        "Make sure it includes http:// or https://.",
    ]


class ContentNotFound(HaulError):
    reason = "The requested content could not be found."
    suggestions = ["Check that the post still exists.", "Verify the URL is correct."]


class PrivateContent(HaulError):
    reason = "The requested content is not publicly accessible."
    suggestions = [
        "Verify that the post or account is public.",
        "HAUL never downloads authenticated or private content.",
    ]


class RateLimited(HaulError):
    reason = "The platform is temporarily rate-limiting requests."
    suggestions = ["Wait a few minutes and try again.", "Reduce --concurrency."]


class NetworkError(HaulError):
    reason = "A network error occurred."
    suggestions = ["Check your internet connection.", "Try again in a moment."]


class ExtractionError(HaulError):
    reason = "HAUL could not read media information from this URL."
    suggestions = [
        "The platform may have changed its page structure.",
        "Try again later, or open an issue with the URL.",
    ]


class DownloadError(HaulError):
    reason = "The download failed."
    suggestions = ["Try again.", "Check your connection and available disk space."]


class FFmpegMissing(HaulError):
    reason = "FFmpeg is required for this operation but was not found on PATH."
    suggestions = [
        "Install FFmpeg: https://ffmpeg.org/download.html",
        "Make sure the 'ffmpeg' command is on your PATH.",
    ]


class HaulPermissionError(HaulError):
    reason = "HAUL does not have permission to write to the destination."
    suggestions = ["Check folder permissions.", "Choose a different --output directory."]


class DiskFull(HaulError):
    reason = "There is not enough disk space to complete this download."
    suggestions = ["Free up disk space.", "Choose a different --output location."]
