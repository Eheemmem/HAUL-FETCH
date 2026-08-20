"""Reddit extractor — videos, images, galleries, and GIFs (spec §3
Tier 1). Reddit gallery posts come back from yt-dlp as a playlist of
entries, which the base adapter already turns into a list of
MediaInfo items (spec §12, "Galleries")."""

from __future__ import annotations

from ..core.extractor import MediaType
from ._shared import YtdlpExtractor


class RedditExtractor(YtdlpExtractor):
    name = "reddit"
    domains = ("reddit.com", "redd.it")

    def _media_type_for(self, data: dict) -> MediaType:
        if data.get("_type") == "playlist":
            return MediaType.GALLERY
        if (data.get("ext") or "").lower() == "gif":
            return MediaType.IMAGE
        return super()._media_type_for(data)
