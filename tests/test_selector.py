"""Unit tests for haul.core.selector — the "never fake 4K" rule
(spec §11) lives here, so it gets the most scrutiny."""

from __future__ import annotations

import pytest

from haul.core.errors import ExtractionError
from haul.core.extractor import MediaFormat
from haul.core.selector import select_best, select_for_quality


def fmt(height, fps=None, bitrate=None, has_audio=True, ext="mp4"):
    return MediaFormat(url=f"https://example.com/{height}p", extension=ext, height=height, fps=fps, bitrate=bitrate, has_audio=has_audio)


def test_select_best_picks_highest_resolution():
    formats = [fmt(360), fmt(1080), fmt(720)]
    assert select_best(formats).height == 1080


def test_select_best_breaks_ties_with_fps():
    formats = [fmt(1080, fps=30), fmt(1080, fps=60)]
    assert select_best(formats).fps == 60


def test_select_best_raises_on_empty_list():
    with pytest.raises(ExtractionError):
        select_best([])


def test_quality_best_ignores_request_ladder():
    formats = [fmt(360), fmt(2160)]
    assert select_for_quality(formats, "best").height == 2160


def test_exact_quality_match():
    formats = [fmt(360), fmt(720), fmt(1080), fmt(2160)]
    assert select_for_quality(formats, "1080p").height == 1080


def test_falls_back_to_closest_lower_quality_when_exact_missing():
    # Source only exposes 720p and 360p; a 1080p request should
    # settle for 720p, never invent a 1080p file.
    formats = [fmt(360), fmt(720)]
    assert select_for_quality(formats, "1080p").height == 720


def test_never_upscales_past_source_maximum():
    # Source maximum is 1080p; a 2160p ("4K") request must still
    # return 1080p rather than claiming a fake 4K result (spec §11).
    formats = [fmt(360), fmt(720), fmt(1080)]
    result = select_for_quality(formats, "2160p")
    assert result.height == 1080


def test_source_at_4k_returns_4k_when_requested():
    formats = [fmt(1080), fmt(2160)]
    result = select_for_quality(formats, "2160p")
    assert result.height == 2160


def test_formats_without_height_fall_back_to_best():
    formats = [fmt(None, ext="jpg")]
    assert select_for_quality(formats, "1080p").extension == "jpg"


def test_empty_formats_raises():
    with pytest.raises(ExtractionError):
        select_for_quality([], "best")
