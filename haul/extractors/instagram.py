"""Instagram extractor — reels, videos, single images, carousels
(spec §3 Tier 1) via yt-dlp. Profile pictures (spec §13) are read
directly from the public profile page, since yt-dlp doesn't expose
that field.

Note: Instagram's public page markup changes without notice, so the
profile-picture path here is best-effort, with a couple of fallback
patterns. If it stops matching, that's a one-file fix in
``extract_profile_picture`` rather than an architecture change —
exactly the kind of thing spec §32's regression-test guidance is for.
"""

from __future__ import annotations

import re

from ..core import errors
from ..core.extractor import MediaFormat, MediaInfo, MediaType
from ..utils.network import build_session
from ._shared import YtdlpExtractor, first_match


class InstagramExtractor(YtdlpExtractor):
    name = "instagram"
    domains = ("instagram.com",)

    def _media_type_for(self, data: dict) -> MediaType:
        if data.get("_type") == "playlist":
            return MediaType.GALLERY
        return super()._media_type_for(data)

    def extract_profile_picture(self, url: str) -> MediaInfo:
        username = self._username_from(url)
        session = build_session()
        try:
            response = session.get(f"https://www.instagram.com/{username}/", timeout=20)
            response.raise_for_status()
        except Exception as e:
            raise errors.ExtractionError(url=url, detail=f"Could not load the profile page: {e}") from e
        finally:
            session.close()

        pic_url = first_match(
            response.text,
            r'"profile_pic_url_hd":"([^"]+)"',
            r'"profile_pic_url":"([^"]+)"',
            r'<meta property="og:image" content="([^"]+)"',
        )
        if not pic_url:
            raise errors.PrivateContent(
                url=url,
                detail=(
                    "Could not find a public profile picture for this account. "
                    "It may be private, or Instagram may have changed its page structure."
                ),
            )
        pic_url = pic_url.encode().decode("unicode_escape")

        return MediaInfo(
            platform=self.name,
            media_type=MediaType.PROFILE_PICTURE,
            id=username,
            source_url=url,
            author=username,
            title=f"{username} profile picture",
            formats=[MediaFormat(url=pic_url, extension="jpg", has_audio=False, format_note="original")],
        )

    @staticmethod
    def _username_from(url: str) -> str:
        match = re.search(r"instagram\.com/([^/?#]+)", url)
        if not match or match.group(1) in {"p", "reel", "reels", "stories", "explore"}:
            raise errors.InvalidURL(url=url, detail="Could not find a username in this Instagram URL.")
        return match.group(1)
