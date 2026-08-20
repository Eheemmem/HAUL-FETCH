"""Holds the set of known extractors and finds the right one for a
URL. Adding a platform means writing an extractor and registering it
in :func:`build_default_registry` — nothing else in HAUL changes
(spec §3, "Architecture requirement").
"""

from __future__ import annotations

from .errors import UnsupportedPlatform
from .extractor import Extractor


class Registry:
    def __init__(self) -> None:
        self._extractors: list[Extractor] = []

    def register(self, extractor: Extractor) -> None:
        self._extractors.append(extractor)

    def find(self, url: str) -> Extractor:
        for extractor in self._extractors:
            if extractor.supports(url):
                return extractor
        raise UnsupportedPlatform(url=url, detail=f"No extractor recognizes this URL: {url}")

    @property
    def platforms(self) -> list[str]:
        return [e.name for e in self._extractors]


def build_default_registry() -> Registry:
    """Wires up all built-in extractors in one place so the CLI and
    tests can both build a fully-populated registry. Imports are
    local so importing this module doesn't require every extractor's
    dependencies to be present (useful for unit-testing in
    isolation)."""
    from ..extractors.facebook import FacebookExtractor
    from ..extractors.instagram import InstagramExtractor
    from ..extractors.pinterest import PinterestExtractor
    from ..extractors.reddit import RedditExtractor
    from ..extractors.tiktok import TikTokExtractor
    from ..extractors.youtube import YouTubeExtractor

    registry = Registry()
    for extractor_cls in (
        InstagramExtractor,
        YouTubeExtractor,
        RedditExtractor,
        PinterestExtractor,
        TikTokExtractor,
        FacebookExtractor,
    ):
        registry.register(extractor_cls())
    return registry
