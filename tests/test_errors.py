"""Unit tests for haul.core.errors — checks that rendered errors
follow the human-readable format from spec §18, not a raw
traceback."""

from __future__ import annotations

from haul.core.errors import ContentNotFound, HaulError, PrivateContent, UnsupportedPlatform


def test_render_includes_reason_and_suggestions():
    err = ContentNotFound(url="https://example.com/post/1")
    text = err.render()
    assert "Reason:" in text
    assert "Try:" in text
    assert "https://example.com/post/1" in text


def test_render_without_url_omits_url_section():
    err = HaulError(detail="Something specific went wrong.")
    text = err.render()
    assert "URL:" not in text
    assert "Something specific went wrong." in text


def test_custom_detail_overrides_generic_reason():
    err = PrivateContent(url="https://example.com/x", detail="This account is private.")
    assert "This account is private." in err.render()
    assert PrivateContent.reason not in err.render()


def test_unsupported_platform_suggests_checking_help():
    err = UnsupportedPlatform(url="https://unknown.example/x")
    text = err.render()
    assert "haul --help" in text
