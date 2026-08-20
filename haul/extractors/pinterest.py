"""Pinterest extractor — pins containing video or image media
(spec §3 Tier 1)."""

from __future__ import annotations

from ._shared import YtdlpExtractor


class PinterestExtractor(YtdlpExtractor):
    name = "pinterest"
    domains = ("pinterest.com", "pin.it")
