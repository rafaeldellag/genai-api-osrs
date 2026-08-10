from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime configuration read from environment variables."""

    wiki_api_url: str = os.getenv(
        "OSRS_WIKI_API_URL", "https://prices.runescape.wiki/api/v1/osrs"
    )
    wiki_user_agent: str = os.getenv(
        "OSRS_USER_AGENT",
        "genai-api-osrs/1.0 (educational project; "
        "github.com/rafaeldellag/genai-api-osrs)",
    )
    request_timeout_seconds: float = float(os.getenv("OSRS_REQUEST_TIMEOUT", "15"))
    mapping_cache_seconds: int = int(os.getenv("OSRS_MAPPING_CACHE_SECONDS", "86400"))
    price_cache_seconds: int = int(os.getenv("OSRS_PRICE_CACHE_SECONDS", "60"))
