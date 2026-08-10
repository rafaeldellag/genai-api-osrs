from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.osrs_client import OSRSPriceClient, PRICE_METHOD, UpstreamServiceError
from app.schemas import (
    ItemSearchResponse,
    ItemView,
    LoadoutRequest,
    LoadoutValueLine,
    LoadoutValueResponse,
)

APP_VERSION = "1.0.0"
STATIC_DIR = Path(__file__).resolve().parent / "static"
EQUIPMENT_SLOTS = {
    "head",
    "cape",
    "neck",
    "ammo",
    "weapon",
    "body",
    "shield",
    "legs",
    "hands",
    "feet",
    "ring",
}
INVENTORY_SLOTS = {str(index) for index in range(28)}


def create_app(price_service: OSRSPriceClient | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        owns_service = application.state.price_service is None
        if owns_service:
            application.state.price_service = OSRSPriceClient()
        yield
        if owns_service:
            await application.state.price_service.close()

    application = FastAPI(
        title="OSRS Loadout Value API",
        description=(
            "Consulta os preços em tempo real da OSRS Wiki e calcula o valor de "
            "equipamentos e inventário."
        ),
        version=APP_VERSION,
        lifespan=lifespan,
    )
    application.state.price_service = price_service

    def get_price_service(request: Request) -> OSRSPriceClient:
        service = request.app.state.price_service
        if service is None:
            # This only occurs when an ASGI test transport skips the lifespan.
            service = OSRSPriceClient()
            request.app.state.price_service = service
        return service

    @application.exception_handler(UpstreamServiceError)
    async def upstream_error_handler(
        _request: Request, exc: UpstreamServiceError
    ) -> JSONResponse:
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    @application.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @application.get("/api/health", tags=["Sistema"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": APP_VERSION}

    @application.get(
        "/api/items", response_model=ItemSearchResponse, tags=["Itens"]
    )
    async def search_items(
        q: str = Query(default="", max_length=80, description="Trecho do nome"),
        limit: int = Query(default=40, ge=1, le=50),
        offset: int = Query(default=0, ge=0),
        service: OSRSPriceClient = Depends(get_price_service),
    ) -> ItemSearchResponse:
        items, total, as_of = await service.search_items(q, limit, offset)
        return ItemSearchResponse(
            items=items, total=total, limit=limit, offset=offset, as_of=as_of
        )

    @application.get("/api/items/{item_id}", response_model=ItemView, tags=["Itens"])
    async def get_item(
        item_id: int,
        service: OSRSPriceClient = Depends(get_price_service),
    ) -> ItemView:
        items, _ = await service.get_items_by_ids({item_id})
        if item_id not in items:
            raise HTTPException(status_code=404, detail="Item não encontrado.")
        return ItemView.model_validate(items[item_id])

    @application.post(
        "/api/loadout/value",
        response_model=LoadoutValueResponse,
        tags=["Loadout"],
    )
    async def calculate_loadout(
        payload: LoadoutRequest,
        service: OSRSPriceClient = Depends(get_price_service),
    ) -> LoadoutValueResponse:
        invalid_slots = [
            f"{entry.area}:{entry.slot}"
            for entry in payload.items
            if (
                entry.area == "equipment"
                and entry.slot not in EQUIPMENT_SLOTS
                or entry.area == "inventory"
                and entry.slot not in INVENTORY_SLOTS
            )
        ]
        if invalid_slots:
            raise HTTPException(
                status_code=422,
                detail=f"Posições inválidas: {', '.join(invalid_slots)}.",
            )

        invalid_quantities = [
            entry.slot
            for entry in payload.items
            if entry.area == "equipment"
            and entry.slot != "ammo"
            and entry.quantity != 1
        ]
        if invalid_quantities:
            raise HTTPException(
                status_code=422,
                detail="Apenas munição equipada pode ter quantidade maior que 1.",
            )

        locations = [(entry.area, entry.slot) for entry in payload.items]
        if len(locations) != len(set(locations)):
            raise HTTPException(
                status_code=422, detail="Cada posição do loadout aceita apenas um item."
            )

        requested_ids = {entry.item_id for entry in payload.items}
        items_by_id, as_of = await service.get_items_by_ids(requested_ids)
        missing_ids = sorted(requested_ids - items_by_id.keys())
        if missing_ids:
            missing = ", ".join(str(item_id) for item_id in missing_ids)
            raise HTTPException(
                status_code=404, detail=f"Itens não encontrados: {missing}."
            )

        lines: list[LoadoutValueLine] = []
        equipment_total = 0
        inventory_total = 0
        priced_lines = 0

        for entry in payload.items:
            item = items_by_id[entry.item_id]
            unit_price = item["price"]
            subtotal = unit_price * entry.quantity if unit_price is not None else 0
            if unit_price is not None:
                priced_lines += 1
            if entry.area == "equipment":
                equipment_total += subtotal
            else:
                inventory_total += subtotal

            lines.append(
                LoadoutValueLine(
                    **item,
                    quantity=entry.quantity,
                    area=entry.area,
                    slot=entry.slot,
                    subtotal=subtotal,
                )
            )

        return LoadoutValueResponse(
            items=lines,
            equipment_total=equipment_total,
            inventory_total=inventory_total,
            grand_total=equipment_total + inventory_total,
            priced_lines=priced_lines,
            unpriced_lines=len(lines) - priced_lines,
            as_of=as_of,
            price_method=PRICE_METHOD,
        )

    application.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return application


app = create_app()
