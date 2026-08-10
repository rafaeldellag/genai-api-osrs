from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


ITEMS = {
    4151: {
        "id": 4151,
        "name": "Abyssal whip",
        "examine": "A weapon from the abyss.",
        "members": True,
        "buy_limit": 70,
        "icon_url": "https://example.test/whip.png",
        "high_price": 1_700_000,
        "low_price": 1_600_000,
        "price": 1_650_000,
        "high_time": 1_700_000_000,
        "low_time": 1_700_000_001,
    },
    995: {
        "id": 995,
        "name": "Coins",
        "examine": "Lovely money!",
        "members": False,
        "buy_limit": None,
        "icon_url": "https://example.test/coins.png",
        "high_price": 1,
        "low_price": 1,
        "price": 1,
        "high_time": 1_700_000_000,
        "low_time": 1_700_000_001,
    },
}


class FakePriceService:
    async def search_items(self, query: str, limit: int, offset: int):
        matches = [
            item for item in ITEMS.values() if query.casefold() in item["name"].casefold()
        ]
        return matches[offset : offset + limit], len(matches), 1_700_000_001

    async def get_items_by_ids(self, item_ids: set[int]):
        return (
            {item_id: ITEMS[item_id] for item_id in item_ids if item_id in ITEMS},
            1_700_000_001,
        )


def make_client() -> TestClient:
    return TestClient(create_app(FakePriceService()))


def test_health_and_frontend_are_served() -> None:
    with make_client() as client:
        health = client.get("/api/health")
        page = client.get("/")

    assert health.status_code == 200
    assert health.json() == {"status": "ok", "version": "1.0.0"}
    assert page.status_code == 200
    assert "Quanto vale o seu loadout?" in page.text


def test_search_filters_items_by_name() -> None:
    with make_client() as client:
        response = client.get("/api/items", params={"q": "whip", "limit": 10})

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["name"] == "Abyssal whip"


def test_loadout_value_sums_equipment_and_inventory() -> None:
    request = {
        "items": [
            {
                "item_id": 4151,
                "quantity": 1,
                "area": "equipment",
                "slot": "weapon",
            },
            {
                "item_id": 995,
                "quantity": 25_000,
                "area": "inventory",
                "slot": "0",
            },
        ]
    }

    with make_client() as client:
        response = client.post("/api/loadout/value", json=request)

    assert response.status_code == 200
    payload = response.json()
    assert payload["equipment_total"] == 1_650_000
    assert payload["inventory_total"] == 25_000
    assert payload["grand_total"] == 1_675_000
    assert payload["priced_lines"] == 2
    assert payload["unpriced_lines"] == 0


def test_loadout_rejects_duplicate_or_invalid_positions() -> None:
    duplicate = {
        "items": [
            {"item_id": 4151, "area": "equipment", "slot": "weapon"},
            {"item_id": 995, "area": "equipment", "slot": "weapon"},
        ]
    }
    invalid = {
        "items": [{"item_id": 995, "area": "inventory", "slot": "28"}]
    }

    with make_client() as client:
        duplicate_response = client.post("/api/loadout/value", json=duplicate)
        invalid_response = client.post("/api/loadout/value", json=invalid)

    assert duplicate_response.status_code == 422
    assert invalid_response.status_code == 422


def test_unknown_item_returns_404() -> None:
    with make_client() as client:
        response = client.get("/api/items/999999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Item não encontrado."
