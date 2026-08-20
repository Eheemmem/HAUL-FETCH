"""Facebook extractor — public videos and images only (spec §3 Tier
1). HAUL never logs in or attempts to access content that requires
authentication; posts on non-public profiles or groups surface as
PrivateContent via the shared yt-dlp adapter's error mapping."""

from __future__ import annotations

from ._shared import YtdlpExtractor


class FacebookExtractor(YtdlpExtractor):
    name = "facebook"
    domains = ("facebook.com", "fb.watch")
