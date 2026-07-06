from fastapi import APIRouter, HTTPException

from ...config import settings
from ...engine.symbol_validation import InvalidSymbolError
from ..schemas import ActiveStockUpdate, EngineStatusRead, NewsFilterUpdate, WatchlistRead

router = APIRouter(prefix="/api/status", tags=["status"])

# Set by main.py during app startup once the EngineRunner exists.
engine_runner = None


@router.get("", response_model=EngineStatusRead)
async def get_status():
    if engine_runner is None:
        raise HTTPException(status_code=503, detail="Engine not running")
    return engine_runner.status_dict()


@router.put("/news-filter", response_model=NewsFilterUpdate)
async def set_news_filter(payload: NewsFilterUpdate):
    settings.news_filter_active = payload.active
    return payload


@router.get("/watchlist", response_model=WatchlistRead)
async def get_watchlist():
    if engine_runner is None:
        raise HTTPException(status_code=503, detail="Engine not running")
    return WatchlistRead(
        leader_symbol=settings.leader_symbol,
        active_symbol=settings.stock_symbol,
        candidates=engine_runner.watchlist.snapshot(),
    )


@router.put("/active-stock", response_model=EngineStatusRead)
async def set_active_stock(payload: ActiveStockUpdate):
    if engine_runner is None:
        raise HTTPException(status_code=503, detail="Engine not running")
    try:
        await engine_runner.set_active_stock(payload.symbol)
    except InvalidSymbolError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return engine_runner.status_dict()
