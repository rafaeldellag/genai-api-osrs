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
    10828: {
        "id": 10828,
        "name": "Helm of neitiznot",
        "examine": "A gift from Neitiznot's Burgher.",
        "members": True,
        "buy_limit": 70,
        "icon_url": "https://example.test/neitiznot.png",
        "high_price": 55_000,
        "low_price": 53_000,
        "price": 54_000,
        "high_time": 1_700_000_000,
        "low_time": 1_700_000_001,
    },
}

EQUIPMENT_SLOTS_BY_ID = {
    4151: frozenset({"weapon"}),
    10828: frozenset({"head"}),
}

EQUIPMENT_SLOT_ICONS = (
    "Ammo_slot.png",
    "Body_slot.png",
    "Cape_slot.png",
    "Feet_slot.png",
    "Hands_slot.png",
    "Head_slot.png",
    "Legs_slot.png",
    "Neck_slot.png",
    "Ring_slot.png",
    "Shield_slot.png",
    "Weapon_slot.png",
)


class FakePriceService:
    async def search_items(
        self, query: str, limit: int, offset: int, equipment_slot: str | None = None
    ):
        matches = [
            item
            for item in ITEMS.values()
            if query.casefold() in item["name"].casefold()
            and (
                equipment_slot is None
                or equipment_slot in EQUIPMENT_SLOTS_BY_ID.get(item["id"], frozenset())
            )
        ]
        return matches[offset : offset + limit], len(matches), 1_700_000_001

    async def get_items_by_ids(self, item_ids: set[int]):
        return (
            {item_id: ITEMS[item_id] for item_id in item_ids if item_id in ITEMS},
            1_700_000_001,
        )

    async def get_equipment_slots_by_ids(self, item_ids: set[int]):
        return {
            item_id: EQUIPMENT_SLOTS_BY_ID[item_id]
            for item_id in item_ids
            if item_id in EQUIPMENT_SLOTS_BY_ID
        }


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
    assert page.headers["content-security-policy"].startswith("default-src 'self'")
    assert page.headers["x-content-type-options"] == "nosniff"
    assert page.headers["x-frame-options"] == "DENY"


def test_untrusted_host_is_rejected() -> None:
    with make_client() as client:
        response = client.get("/api/health", headers={"host": "attacker.invalid"})

    assert response.status_code == 400


def test_equipment_slot_icons_are_served_and_referenced() -> None:
    with make_client() as client:
        script = client.get("/static/app.js")
        icons = {
            filename: client.get(f"/static/equipment-slots/{filename}")
            for filename in EQUIPMENT_SLOT_ICONS
        }

    assert script.status_code == 200
    for filename, response in icons.items():
        assert filename in script.text
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert response.content.startswith(b"\x89PNG\r\n\x1a\n")
        assert int.from_bytes(response.content[16:20]) == 36
        assert int.from_bytes(response.content[20:24]) == 36


def test_search_filters_items_by_name() -> None:
    with make_client() as client:
        response = client.get("/api/items", params={"q": "whip", "limit": 10})

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["name"] == "Abyssal whip"


def test_search_filters_equipment_by_slot() -> None:
    with make_client() as client:
        head_response = client.get("/api/items", params={"slot": "head"})
        weapon_response = client.get("/api/items", params={"slot": "weapon"})
        invalid_response = client.get("/api/items", params={"slot": "backpack"})

    assert head_response.status_code == 200
    assert [item["name"] for item in head_response.json()["items"]] == [
        "Helm of neitiznot"
    ]
    assert weapon_response.status_code == 200
    assert [item["name"] for item in weapon_response.json()["items"]] == [
        "Abyssal whip"
    ]
    assert invalid_response.status_code == 422


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


def test_loadout_rejects_item_in_wrong_equipment_slot() -> None:
    request = {
        "items": [
            {
                "item_id": 4151,
                "area": "equipment",
                "slot": "head",
            }
        ]
    }

    with make_client() as client:
        response = client.post("/api/loadout/value", json=request)

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "Itens incompatíveis com as posições: Abyssal whip em head."
    )


def test_unknown_item_returns_404() -> None:
    with make_client() as client:
        response = client.get("/api/items/999999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Item não encontrado."
