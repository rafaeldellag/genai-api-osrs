from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx

from app.config import Settings
from app.equipment import EQUIPMENT_SLOTS, EquipmentSlot, normalize_wiki_slot


PRICE_METHOD = (
    "Média entre a compra instantânea (high) e a venda instantânea (low); "
    "quando apenas uma existe, ela é usada."
)

# These appear first when the picker opens without a search term. Everything else
# remains available directly after them or through name search.
FEATURED_ITEM_IDS = (
    4151,   # Abyssal whip
    11840,  # Dragon boots
    6570,   # Fire cape
    12926,  # Toxic blowpipe
    22322,  # Avernic defender
    11802,  # Armadyl godsword
    19547,  # Necklace of anguish
    11283,  # Dragonfire shield
    6737,   # Berserker ring
    12002,  # Occult necklace
)

EQUIPMENT_PAGE_SIZE = 5_000


class UpstreamServiceError(RuntimeError):
    """Raised when the Wiki price service cannot provide usable data."""


@dataclass(slots=True)
class CacheEntry:
    value: Any
    expires_at: float


class OSRSPriceClient:
    """Small async client with polite headers and in-memory response caching."""

    def __init__(
        self,
        settings: Settings | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings or Settings()
        self._client = httpx.AsyncClient(
            base_url=self.settings.wiki_api_url.rstrip("/"),
            headers={
                "User-Agent": self.settings.wiki_user_agent,
                "Accept": "application/json",
            },
            timeout=self.settings.request_timeout_seconds,
            follow_redirects=True,
            transport=transport,
        )
        self._cache: dict[str, CacheEntry] = {}
        self._locks = {"mapping": asyncio.Lock(), "latest": asyncio.Lock()}

    async def close(self) -> None:
        await self._client.aclose()

    async def _cached_request(self, key: str, path: str, ttl: int) -> Any:
        now = time.monotonic()
        cached = self._cache.get(key)
        if cached and cached.expires_at > now:
            return cached.value

        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            now = time.monotonic()
            cached = self._cache.get(key)
            if cached and cached.expires_at > now:
                return cached.value

            try:
                response = await self._client.get(path)
                response.raise_for_status()
                payload = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                # A stale response is safer and more useful than taking the whole
                # application down during a brief upstream outage.
                if cached:
                    return cached.value
                raise UpstreamServiceError(
                    "Não foi possível consultar a API de preços da OSRS Wiki."
                ) from exc

            self._cache[key] = CacheEntry(value=payload, expires_at=now + ttl)
            return payload

    def _equipment_api_url(self, offset: int) -> str:
        query = (
            'bucket("infobox_bonuses")'
            '.select("equipment_slot", "infobox_item.item_id")'
            '.join("infobox_item", "infobox_item.page_name_sub", '
            '"infobox_bonuses.page_name_sub")'
            '.where("infobox_item.tradeable", true)'
            f".limit({EQUIPMENT_PAGE_SIZE}).offset({offset}).run()"
        )
        return str(
            httpx.URL(
                self.settings.wiki_data_api_url,
                params={
                    "action": "bucket",
                    "format": "json",
                    "formatversion": "2",
                    "query": query,
                },
            )
        )

    async def _equipment_slot_data(self) -> dict[int, frozenset[str]]:
        slots_by_id: dict[int, set[str]] = {}
        offset = 0

        while True:
            payload = await self._cached_request(
                f"equipment:{offset}",
                self._equipment_api_url(offset),
                self.settings.equipment_cache_seconds,
            )
            rows = payload.get("bucket") if isinstance(payload, dict) else None
            if not isinstance(rows, list):
                raise UpstreamServiceError(
                    "A OSRS Wiki retornou dados de equipamento inválidos."
                )

            for row in rows:
                if not isinstance(row, dict):
                    continue
                raw_slot = row.get("equipment_slot")
                raw_ids = row.get("infobox_item.item_id")
                if not isinstance(raw_slot, str) or not isinstance(raw_ids, list):
                    continue

                slot = normalize_wiki_slot(raw_slot)
                if slot not in EQUIPMENT_SLOTS:
                    continue

                for raw_id in raw_ids:
                    try:
                        item_id = int(raw_id)
                    except (TypeError, ValueError):
                        continue
                    slots_by_id.setdefault(item_id, set()).add(slot)

            if len(rows) < EQUIPMENT_PAGE_SIZE:
                break
            offset += EQUIPMENT_PAGE_SIZE

        return {
            item_id: frozenset(slots) for item_id, slots in slots_by_id.items()
        }

    async def get_equipment_slots_by_ids(
        self, item_ids: set[int]
    ) -> dict[int, frozenset[str]]:
        if not item_ids:
            return {}
        slots_by_id = await self._equipment_slot_data()
        return {
            item_id: slots_by_id[item_id]
            for item_id in item_ids
            if item_id in slots_by_id
        }

    async def _catalog_data(self) -> tuple[list[dict[str, Any]], dict[str, Any], int | None]:
        mapping_payload, latest_payload = await asyncio.gather(
            self._cached_request(
                "mapping", "/mapping", self.settings.mapping_cache_seconds
            ),
            self._cached_request("latest", "/latest", self.settings.price_cache_seconds),
        )

        if not isinstance(mapping_payload, list):
            raise UpstreamServiceError("A OSRS Wiki retornou um catálogo inválido.")

        latest = latest_payload.get("data") if isinstance(latest_payload, dict) else None
        if not isinstance(latest, dict):
            raise UpstreamServiceError("A OSRS Wiki retornou preços inválidos.")

        timestamps = [
            value
            for prices in latest.values()
            if isinstance(prices, dict)
            for value in (prices.get("highTime"), prices.get("lowTime"))
            if isinstance(value, int)
        ]
        return mapping_payload, latest, max(timestamps, default=None)

    @staticmethod
    def estimate_price(high: int | None, low: int | None) -> int | None:
        valid_prices = [value for value in (high, low) if isinstance(value, int)]
        if not valid_prices:
            return None
        return round(sum(valid_prices) / len(valid_prices))

    @staticmethod
    def _icon_url(icon_name: str) -> str:
        filename = quote(icon_name.replace(" ", "_"), safe="")
        return f"https://oldschool.runescape.wiki/w/Special:Redirect/file/{filename}"

    def _merge_item(
        self, metadata: dict[str, Any], prices: dict[str, Any] | None
    ) -> dict[str, Any]:
        prices = prices if isinstance(prices, dict) else {}
        high = prices.get("high") if isinstance(prices.get("high"), int) else None
        low = prices.get("low") if isinstance(prices.get("low"), int) else None
        icon = metadata.get("icon") if isinstance(metadata.get("icon"), str) else ""

        return {
            "id": int(metadata["id"]),
            "name": str(metadata.get("name", "Item desconhecido")),
            "examine": str(metadata.get("examine", "")),
            "members": bool(metadata.get("members", False)),
            "buy_limit": metadata.get("limit")
            if isinstance(metadata.get("limit"), int)
            else None,
            "icon_url": self._icon_url(icon),
            "high_price": high,
            "low_price": low,
            "price": self.estimate_price(high, low),
            "high_time": prices.get("highTime")
            if isinstance(prices.get("highTime"), int)
            else None,
            "low_time": prices.get("lowTime")
            if isinstance(prices.get("lowTime"), int)
            else None,
        }

    async def search_items(
        self,
        query: str,
        limit: int,
        offset: int,
        equipment_slot: EquipmentSlot | None = None,
    ) -> tuple[list[dict[str, Any]], int, int | None]:
        if equipment_slot is None:
            mapping, latest, as_of = await self._catalog_data()
            slots_by_id: dict[int, frozenset[str]] = {}
        else:
            catalog, slots_by_id = await asyncio.gather(
                self._catalog_data(), self._equipment_slot_data()
            )
            mapping, latest, as_of = catalog
        normalized_query = query.strip().casefold()

        candidates = [
            item
            for item in mapping
            if isinstance(item, dict)
            and isinstance(item.get("id"), int)
            and isinstance(item.get("name"), str)
            and (not normalized_query or normalized_query in item["name"].casefold())
            and (
                equipment_slot is None
                or equipment_slot in slots_by_id.get(item["id"], frozenset())
            )
        ]

        if normalized_query:
            candidates.sort(
                key=lambda item: (
                    not item["name"].casefold().startswith(normalized_query),
                    item["name"].casefold().find(normalized_query),
                    len(item["name"]),
                    item["name"].casefold(),
                )
            )
        else:
            featured_rank = {
                item_id: rank for rank, item_id in enumerate(FEATURED_ITEM_IDS)
            }
            candidates.sort(
                key=lambda item: (
                    item["id"] not in featured_rank,
                    featured_rank.get(item["id"], 0),
                    item["name"].casefold(),
                )
            )

        page = candidates[offset : offset + limit]
        items = [
            self._merge_item(item, latest.get(str(item["id"]))) for item in page
        ]
        return items, len(candidates), as_of

    async def get_items_by_ids(
        self, item_ids: set[int]
    ) -> tuple[dict[int, dict[str, Any]], int | None]:
        if not item_ids:
            return {}, None

        mapping, latest, as_of = await self._catalog_data()
        metadata_by_id = {
            item["id"]: item
            for item in mapping
            if isinstance(item, dict) and item.get("id") in item_ids
        }
        merged = {
            item_id: self._merge_item(metadata, latest.get(str(item_id)))
            for item_id, metadata in metadata_by_id.items()
        }
        return merged, as_of
