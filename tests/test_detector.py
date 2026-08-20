"""Unit tests for haul.core.detector. Uses small fake extractors
rather than the real platform ones so this file tests only the
detection/routing logic, independent of yt-dlp (spec §32, "Unit
tests" vs "Integration tests")."""

from __future__ import annotations

import pytest

from haul.core.detector import detect, validate_url
from haul.core.errors import InvalidURL, UnsupportedPlatform
from haul.core.extractor import Extractor
from haul.core.registry import Registry


class _FakeExtractor(Extractor):
    def __init__(self, name: str, domain: str):
        self.name = name
        self.domain = domain

    def supports(self, url: str) -> bool:
        return self.domain in url

    def extract(self, url: str):
        raise NotImplementedError


@pytest.fixture
def registry():
    reg = Registry()
    reg.register(_FakeExtractor("alpha", "alpha.com"))
    reg.register(_FakeExtractor("beta", "beta.com"))
    return reg


@pytest.mark.parametrize(
    "url",
    [
        "not a url",
        "ftp://example.com/file",
        "example.com/no-scheme",
        "",
        "   ",
    ],
)
def test_validate_url_rejects_invalid(url):
    with pytest.raises(InvalidURL):
        validate_url(url)


@pytest.mark.parametrize("url", ["https://example.com/x", "http://example.com/x"])
def test_validate_url_accepts_http_and_https(url):
    assert validate_url(url) == url


def test_validate_url_strips_whitespace():
    assert validate_url("  https://example.com/x  ") == "https://example.com/x"


def test_detect_routes_to_matching_extractor(registry):
    extractor = detect("https://alpha.com/post/1", registry)
    assert extractor.name == "alpha"


def test_detect_raises_for_unknown_platform(registry):
    with pytest.raises(UnsupportedPlatform):
        detect("https://unknown-platform.com/post/1", registry)


def test_detect_raises_invalid_url_before_checking_platform(registry):
    with pytest.raises(InvalidURL):
        detect("not-a-url-at-all", registry)


def test_registry_platforms_lists_registered_names(registry):
    assert registry.platforms == ["alpha", "beta"]
