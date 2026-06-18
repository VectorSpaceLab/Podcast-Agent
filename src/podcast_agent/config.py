"""Runtime configuration helpers."""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

DEFAULT_OUTPUT_DIR = os.getenv("DEFAULT_OUTPUT_DIR", "output")
YOUTUBE_COOKIES_FILE = os.getenv("YOUTUBE_COOKIES_FILE") or None
BILIBILI_COOKIES_FILE = os.getenv("BILIBILI_COOKIES_FILE") or None
BILIBILI_USER_AGENT = os.getenv("BILIBILI_USER_AGENT") or None
