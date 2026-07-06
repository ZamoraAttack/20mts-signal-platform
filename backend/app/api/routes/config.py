from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from . import status as status_routes
from ...config import settings
from ...database import AsyncSessionLocal
from ...models import StrategyConfig
from ..schemas import ConfigItem, ConfigUpdate

router = APIRouter(prefix="/api/config", tags=["config"])

# Maps strategy_config keys to (Settings attribute name, type caster).
# Updating a row here also updates the live Settings singleton, so the
# running signal engine picks up the new threshold on its next tick —
# no restart required.
CONFIG_FIELD_MAP: dict[str, tuple[str, type]] = {
    "sync_window_seconds": ("sync_window_seconds", int),
    "sync_correlation_threshold": ("sync_correlation_threshold", float),
    "joint_decline_window_seconds": ("joint_decline_window_seconds", int),
    "joint_decline_min_return": ("joint_decline_min_return", float),
    "ema_period_seconds": ("ema_period_seconds", int),
    "divergence_dia_consecutive_ticks": ("divergence_dia_consecutive_ticks", int),
    "divergence_return_window_seconds": ("divergence_return_window_seconds", int),
    "divergence_expiry_seconds": ("divergence_expiry_seconds", int),
    "reconnection_consecutive_ticks": ("reconnection_consecutive_ticks", int),
    "reconnection_lookback_seconds": ("reconnection_lookback_seconds", int),
    "watchlist_symbols": ("watchlist_symbols", str),
}
# leader_symbol / stock_symbol are deliberately NOT in this map: switching
# the active stock must go through EngineRunner.set_active_stock() so the
# state machine resets to a fresh pairing (see routes/status.py). A bare
# setattr via this generic config path would leave stale buffers/state
# mixing old-stock and new-stock ticks.


@router.get("", response_model=list[ConfigItem])
async def list_config():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(StrategyConfig).order_by(StrategyConfig.key))
        return result.scalars().all()


@router.put("/{key}", response_model=ConfigItem)
async def update_config(key: str, payload: ConfigUpdate):
    if key not in CONFIG_FIELD_MAP:
        raise HTTPException(status_code=404, detail=f"Unknown config key: {key}")

    attr_name, caster = CONFIG_FIELD_MAP[key]
    try:
        typed_value = caster(payload.value)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid value for {key}: {payload.value!r}")

    async with AsyncSessionLocal() as db:
        config_row = await db.get(StrategyConfig, key)
        if config_row is None:
            raise HTTPException(status_code=404, detail=f"Unknown config key: {key}")

        config_row.value = payload.value
        config_row.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(config_row)

    setattr(settings, attr_name, typed_value)

    if key == "watchlist_symbols" and status_routes.engine_runner is not None:
        # The feed only delivers ticks for symbols it's subscribed to --
        # re-subscribe so newly-added watchlist candidates actually stream.
        await status_routes.engine_runner.feed_manager.resubscribe()

    return config_row
