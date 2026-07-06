"""
Schwab Trader API data feed (REST quote polling).

Prerequisites before this feed can be used:
  1. Apply for "Market Data Production" access at developer.schwab.com
  2. Set SCHWAB_CLIENT_ID and SCHWAB_CLIENT_SECRET in .env
  3. Run `python -m app.schwab.auth_setup` to complete the OAuth2 flow
     (writes schwab_tokens.json)

Implementation note (transparency per project directive):
  Schwab's Trader API also offers a WebSocket streaming endpoint that
  delivers Level 1 equity quotes at tick frequency. Its exact protocol
  (login handshake, field-number maps, heartbeats) is documented only
  behind Market Data Production approval, which this account does not yet
  have — so rather than guess at that protocol, this feed polls the
  publicly-documented REST quotes endpoint (`/marketdata/v1/quotes`) on a
  fixed interval (`settings.schwab_poll_interval_seconds`, default 1s) and
  emits the same `Tick` objects as SimulatedFeed. This can be swapped for
  true streaming later, once the streaming protocol is confirmed against
  real docs — nothing downstream (state machine, API, dashboard) needs to
  change.

  Symbol note: this same /marketdata/v1/quotes endpoint is expected (per
  Schwab's public docs) to also accept index symbols like "$DJI" for the
  real Dow Jones Industrial Average, not just equity/ETF tickers — also
  unverified pending Market Data Production approval. No code change is
  needed here either way; self._symbols is passed straight through.
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Optional

import httpx

from ..config import settings
from ..schwab.auth import SchwabAuth
from .base import DataFeed, Tick

logger = logging.getLogger(__name__)

QUOTES_URL = "https://api.schwabapi.com/marketdata/v1/quotes"


class SchwabFeed(DataFeed):

    def __init__(self) -> None:
        self._auth: Optional[SchwabAuth] = None
        self._client: Optional[httpx.AsyncClient] = None
        self._symbols: list[str] = []
        self._running = False

    async def connect(self) -> None:
        if not settings.schwab_client_id or not settings.schwab_client_secret:
            raise RuntimeError(
                "Schwab API credentials not configured. "
                "Set SCHWAB_CLIENT_ID and SCHWAB_CLIENT_SECRET in .env, "
                "then run `python -m app.schwab.auth_setup` to complete authorization."
            )
        self._auth = SchwabAuth(
            client_id=settings.schwab_client_id,
            client_secret=settings.schwab_client_secret,
            redirect_uri=settings.schwab_redirect_uri,
            tokens_path=settings.schwab_tokens_path,
        )
        self._client = httpx.AsyncClient(timeout=10.0)
        self._running = True
        logger.info("Schwab feed connected (REST polling mode)")

    async def subscribe(self, symbols: list[str]) -> None:
        self._symbols = symbols

    async def stream(self) -> AsyncIterator[Tick]:
        assert self._auth is not None and self._client is not None

        while self._running:
            # Recomputed every poll (not hoisted above the loop) so a live
            # subscribe() call -- e.g. an active-stock switch -- takes
            # effect on the next poll instead of requiring a reconnect.
            symbols_param = ",".join(self._symbols)
            access_token = await self._auth.get_access_token()
            resp = await self._client.get(
                QUOTES_URL,
                params={"symbols": symbols_param, "fields": "quote"},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if resp.status_code != 200:
                logger.error(
                    "Schwab quotes request failed (HTTP %s): %s", resp.status_code, resp.text
                )
                await asyncio.sleep(settings.schwab_poll_interval_seconds)
                continue

            data = resp.json()
            now = datetime.now(timezone.utc)
            for symbol in self._symbols:
                entry = data.get(symbol)
                if not entry or "quote" not in entry:
                    continue
                quote = entry["quote"]
                last_price = quote.get("lastPrice")
                if last_price is None:
                    continue

                quote_time_ms = quote.get("quoteTime")
                ts = (
                    datetime.fromtimestamp(quote_time_ms / 1000, tz=timezone.utc)
                    if quote_time_ms
                    else now
                )

                yield Tick(
                    symbol=symbol,
                    price=float(last_price),
                    timestamp=ts,
                    volume=quote.get("totalVolume"),
                    bid=quote.get("bidPrice"),
                    ask=quote.get("askPrice"),
                )

            await asyncio.sleep(settings.schwab_poll_interval_seconds)

    async def disconnect(self) -> None:
        self._running = False
        if self._client is not None:
            await self._client.aclose()
