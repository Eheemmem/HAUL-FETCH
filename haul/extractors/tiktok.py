"""TikTok extractor — videos and image posts (slideshows), spec §3
Tier 1. A TikTok image-post slideshow comes back from yt-dlp as a
playlist, same as an Instagram carousel or Reddit gallery."""

from __future__ import annotations

from ..core.extractor import MediaType
from ._shared import YtdlpExtractor


class TikTokExtractor(YtdlpExtractor):
    name = "tiktok"
    domains = ("tiktok.com",)

    def _media_type_for(self, data: dict) -> MediaType:
        if data.get("_type") == "playlist":
            return MediaType.GALLERY
        return super()._media_type_for(data)
