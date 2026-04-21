from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse


YOUTUBE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def extract_video_id(url: str) -> str:
    parsed = urlparse(url.strip())
    host = parsed.netloc.lower()
    path = parsed.path.strip("/")

    if host in {"youtu.be", "www.youtu.be"}:
        candidate = path.split("/")[0]
        if YOUTUBE_ID_RE.match(candidate):
            return candidate

    if "youtube.com" in host:
        query_id = parse_qs(parsed.query).get("v", [""])[0]
        if YOUTUBE_ID_RE.match(query_id):
            return query_id

        parts = path.split("/")
        for prefix in ("shorts", "embed", "live"):
            if len(parts) >= 2 and parts[0] == prefix and YOUTUBE_ID_RE.match(parts[1]):
                return parts[1]

    raise ValueError("Only single YouTube video, shorts, embed, live, or youtu.be URLs are supported.")


def is_youtube_url(url: str) -> bool:
    try:
        extract_video_id(url)
    except ValueError:
        return False
    return True

