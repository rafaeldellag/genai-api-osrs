from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ItemView(BaseModel):
    id: int
    name: str
    examine: str
    members: bool
    buy_limit: int | None = None
    icon_url: str
    high_price: int | None = None
    low_price: int | None = None
    price: int | None = None
    high_time: int | None = None
    low_time: int | None = None


class ItemSearchResponse(BaseModel):
    items: list[ItemView]
    total: int
    limit: int
    offset: int
    as_of: int | None = None


class LoadoutItem(BaseModel):
    item_id: int = Field(gt=0)
    quantity: int = Field(default=1, ge=1, le=2_147_483_647)
    area: Literal["equipment", "inventory"]
    slot: str = Field(min_length=1, max_length=24)


class LoadoutRequest(BaseModel):
    items: list[LoadoutItem] = Field(default_factory=list, max_length=39)


class LoadoutValueLine(ItemView):
    quantity: int
    area: Literal["equipment", "inventory"]
    slot: str
    subtotal: int


class LoadoutValueResponse(BaseModel):
    items: list[LoadoutValueLine]
    equipment_total: int
    inventory_total: int
    grand_total: int
    priced_lines: int
    unpriced_lines: int
    as_of: int | None = None
    currency: Literal["coins"] = "coins"
    price_method: str
