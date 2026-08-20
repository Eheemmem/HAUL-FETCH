"""URL validation and platform detection (spec §20 "URL Detector").

This module answers two questions before anything else happens: is
this actually a URL, and which extractor should handle it? Nothing
here downloads or extracts anything.
"""

from __future__ import annotations

from urllib.parse import urlparse

from .errors import InvalidURL
from .extractor import Extractor
from .registry import Registry


def validate_url(url: str) -> str:
    """Raises InvalidURL for anything that isn't a well-formed
    http(s) URL; otherwise returns the trimmed URL."""
    candidate = url.strip()
    parsed = urlparse(candidate)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise InvalidURL(url=url, detail=f"'{url}' does not look like a valid http(s) URL.")
    return candidate


def detect(url: str, registry: Registry) -> Extractor:
    """Validates the URL, then asks the registry which extractor
    claims it. Raises InvalidURL or UnsupportedPlatform."""
    validated = validate_url(url)
    return registry.find(validated)
