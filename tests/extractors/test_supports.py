"""Unit tests for each extractor's supports() method — the part of
every extractor that decides "is this URL mine?" This never hits the
network, so it runs as part of the normal (non-integration) suite.
"""

from __future__ import annotations

import pytest

from haul.extractors.facebook import FacebookExtractor
from haul.extractors.instagram import InstagramExtractor
from haul.extractors.pinterest import PinterestExtractor
from haul.extractors.reddit import RedditExtractor
from haul.extractors.tiktok import TikTokExtractor
from haul.extractors.youtube import YouTubeExtractor

CASES = [
    (InstagramExtractor, "https://www.instagram.com/reel/ABC123/", True),
    (InstagramExtractor, "https://instagram.com/p/ABC123/", True),
    (InstagramExtractor, "https://youtube.com/watch?v=1", False),
    (YouTubeExtractor, "https://www.youtube.com/watch?v=dQw4w9WgXcQ", True),
    (YouTubeExtractor, "https://youtu.be/dQw4w9WgXcQ", True),
    (YouTubeExtractor, "https://m.youtube.com/shorts/abc123", True),
    (YouTubeExtractor, "https://vimeo.com/12345", False),
    (RedditExtractor, "https://www.reddit.com/r/example/comments/789/title/", True),
    (RedditExtractor, "https://redd.it/789", True),
    (RedditExtractor, "https://reddit.co/fake", False),
    (PinterestExtractor, "https://www.pinterest.com/pin/12345/", True),
    (PinterestExtractor, "https://pin.it/abc123", True),
    (TikTokExtractor, "https://www.tiktok.com/@user/video/12345", True),
    (TikTokExtractor, "https://vm.tiktok.com/abc123/", True),  # subdomain short-link, still *.tiktok.com
    (TikTokExtractor, "https://tiktok.co/fake", False),
    (FacebookExtractor, "https://www.facebook.com/watch/?v=12345", True),
    (FacebookExtractor, "https://fb.watch/abc123/", True),
    (FacebookExtractor, "https://facebook.co/fake", False),
]


@pytest.mark.parametrize("extractor_cls,url,expected", CASES)
def test_supports(extractor_cls, url, expected):
    assert extractor_cls().supports(url) is expected


def test_extractors_only_claim_their_own_domain():
    # No extractor should accidentally claim a URL from a different
    # platform's domain.
    extractors = [cls() for cls in (InstagramExtractor, YouTubeExtractor, RedditExtractor, PinterestExtractor, TikTokExtractor, FacebookExtractor)]
    url = "https://www.instagram.com/reel/ABC123/"
    matches = [e.name for e in extractors if e.supports(url)]
    assert matches == ["instagram"]
