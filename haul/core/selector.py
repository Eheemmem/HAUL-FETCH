"""Picks the best MediaFormat for a requested quality (spec §10).

This is the only place in HAUL that ranks formats, so the "never
upscale, never fake 4K" rule (spec §11) lives in exactly one
function: if the requested quality doesn't exist, HAUL falls back to
the closest *lower* quality that is actually available. It never
reaches for something higher than the source exposes.
"""

from __future__ import annotations

from .errors import ExtractionError
from .extractor import MediaFormat

QUALITY_LADDER = ["2160p", "1440p", "1080p", "720p", "480p", "360p"]


def _height_of(quality: str) -> int:
    return int(quality.rstrip("p"))


def rank_key(fmt: MediaFormat) -> tuple:
    """Higher sorts better. Ranks by resolution, then frame rate,
    then bitrate, then whether audio is already attached — never by
    anything that would imply upscaling or re-encoding."""
    return (fmt.height or 0, fmt.fps or 0, fmt.bitrate or 0, 1 if fmt.has_audio else 0)


def select_best(formats: list[MediaFormat]) -> MediaFormat:
    if not formats:
        raise ExtractionError(detail="No downloadable formats were found for this media.")
    return max(formats, key=rank_key)


def select_for_quality(formats: list[MediaFormat], quality: str) -> MediaFormat:
    """``quality`` is ``"best"`` or one of QUALITY_LADDER.

    HAUL never invents a higher quality than the source exposes: if
    the exact request can't be met, this falls back to the highest
    quality at or below the request. If the request is higher than
    anything available, it returns the highest native quality that
    exists — never an upscale (spec §11).
    """
    if not formats:
        raise ExtractionError(detail="No downloadable formats were found for this media.")

    if quality == "best":
        return select_best(formats)

    requested_height = _height_of(quality)
    with_height = [f for f in formats if f.height]
    if not with_height:
        # Nothing exposes a resolution to compare against (e.g. a
        # single static image with only one representation).
        return select_best(formats)

    at_or_below = [f for f in with_height if f.height <= requested_height]
    if at_or_below:
        return max(at_or_below, key=rank_key)

    return max(with_height, key=rank_key)
