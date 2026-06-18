"""Bilibili source URL parsing."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from podcast_agent.errors import InvalidSourceUrlError
from podcast_agent.types import SourceRef


_BVID_RE = re.compile(r"^BV[0-9A-Za-z]+$")


def _validate_bilibili_id(source_id: str, url: str) -> str:
    source_id = source_id.strip()
    if not source_id or "/" in source_id:
        raise InvalidSourceUrlError(f"Invalid Bilibili video URL: {url}")
    return source_id


def extract_bilibili_id(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    path_parts = [part for part in parsed.path.split("/") if part]

    if host == "b23.tv":
        if path_parts:
            return _validate_bilibili_id(path_parts[0], url)
        raise InvalidSourceUrlError(f"Invalid Bilibili video URL: {url}")

    if host == "bilibili.com" or host.endswith(".bilibili.com"):
        for part in path_parts:
            if _BVID_RE.fullmatch(part):
                return _validate_bilibili_id(part, url)

    raise InvalidSourceUrlError(f"Invalid Bilibili video URL: {url}")


class BilibiliSourceClient:
    source_type = "bilibili"

    def resolve(self, url: str) -> SourceRef:
        return SourceRef(
            source_type=self.source_type,
            url=url,
            source_id=extract_bilibili_id(url),
        )
