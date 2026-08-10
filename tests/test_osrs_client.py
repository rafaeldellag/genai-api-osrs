from __future__ import annotations

import asyncio
import json

import httpx

from app.config import Settings
from app.osrs_client import OSRSPriceClient


def test_estimate_price_uses_both_sides_when_available() -> None:
    assert OSRSPriceClient.estimate_price(120, 100) == 110
    assert OSRSPriceClient.estimate_price(120, None) == 120
    assert OSRSPriceClient.estimate_price(None, 100) == 100
    assert OSRSPriceClient.estimate_price(None, None) is None


def test_wiki_responses_are_merged_and_cached() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["User-Agent"].startswith("test-agent")
        if request.url.path.endswith("/mapping"):
            payload = [
                {
                    "id": 4151,
                    "name": "Abyssal whip",
                    "examine": "A weapon from the abyss.",
                    "members": True,
                    "limit": 70,
                    "icon": "Abyssal whip.png",
                }
            ]
        else:
            payload = {
                "data": {
                    "4151": {
                        "high": 1_700_000,
                        "highTime": 1_700_000_010,
                        "low": 1_600_000,
                        "lowTime": 1_700_000_000,
                    }
                }
            }
        return httpx.Response(200, content=json.dumps(payload), request=request)

    async def scenario() -> None:
        service = OSRSPriceClient(
            Settings(
                wiki_api_url="https://prices.example.test/api/v1/osrs",
                wiki_user_agent="test-agent/1.0",
                request_timeout_seconds=2,
                mapping_cache_seconds=60,
                price_cache_seconds=60,
            ),
            transport=httpx.MockTransport(handler),
        )
        first, total, as_of = await service.search_items("whip", 10, 0)
        second, _, _ = await service.search_items("whip", 10, 0)
        await service.close()

        assert total == 1
        assert as_of == 1_700_000_010
        assert first[0]["price"] == 1_650_000
        assert first[0]["icon_url"].endswith("Abyssal_whip.png")
        assert second == first

    asyncio.run(scenario())
    assert len(requests) == 2
