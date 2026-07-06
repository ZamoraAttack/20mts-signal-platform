from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://twentymts:twentymts@localhost:5432/twentymts"

    # Instruments
    # leader_symbol: the "Dow" side of the comparison. The correct value
    # depends on data_feed_provider:
    #   - "schwab" (live): set LEADER_SYMBOL=$DJI in .env to use the real
    #     DJI index directly via Schwab's /marketdata/v1/quotes endpoint
    #     (Schwab's public docs indicate index symbols like $DJI are
    #     supported there) -- UNVERIFIED, since Market Data Production
    #     access is still pending approval. Re-verify once approved.
    #   - "replay" (Databento backtesting): must stay "DIA". Databento's
    #     EQUS.MINI dataset is equities/ETFs only -- it has no $DJI index
    #     ticks and no Dow futures, so DIA is the only Dow proxy actually
    #     obtainable through that dataset, not a placeholder for something
    #     better later.
    #   - "simulated": DIA is just a synthetic label, value doesn't matter.
    leader_symbol: str = "DIA"
    stock_symbol: str = "AAPL"

    # Candidate stocks passively screened for correlation vs leader_symbol,
    # in addition to whichever one is currently stock_symbol (the active,
    # traded pairing). Comma-separated (plain str, not list[str]) to avoid
    # pydantic-settings' JSON-parsing expectations for list-typed env vars.
    watchlist_symbols: str = ""

    @property
    def watchlist_symbol_list(self) -> list[str]:
        return [s.strip() for s in self.watchlist_symbols.split(",") if s.strip()]

    # Synchronization regime filter
    sync_window_seconds: int = 300
    sync_correlation_threshold: float = 0.70
    # Hysteresis: once synchronized, correlation must drop below this LOWER
    # threshold (not just below sync_correlation_threshold) to lose sync.
    # Without this, correlation hovering near sync_correlation_threshold
    # causes the synchronized state to flicker on/off every second.
    sync_correlation_exit_threshold: float = 0.60
    # Correlation is computed on N-second returns (price now vs price N seconds
    # ago) rather than literal 1-second tick-to-tick returns, to filter out
    # second-to-second price noise and match "are these two generally moving
    # the same direction" as seen on a 1-second chart.
    correlation_return_lag_seconds: int = 5

    # Joint decline
    joint_decline_window_seconds: int = 12
    joint_decline_min_return: float = -0.0005
    ema_period_seconds: int = 25

    # Divergence
    divergence_dia_consecutive_ticks: int = 3
    divergence_return_window_seconds: int = 5
    divergence_expiry_seconds: int = 120

    # Reconnection
    reconnection_consecutive_ticks: int = 2
    reconnection_lookback_seconds: int = 10

    # Market hours (ET)
    market_open_hour: int = 9
    market_open_minute: int = 30
    market_close_hour: int = 16
    market_close_minute: int = 0
    high_volatility_window_minutes: int = 30

    # Manual news filter toggle
    news_filter_active: bool = False

    # Dev/testing: when false, FeedManager processes ticks regardless of
    # market hours (so SimulatedFeed is usable outside 9:30-16:00 ET).
    # Should remain true once trading against the real Schwab feed.
    respect_market_hours: bool = True

    # Data feed: "simulated" (default, dev/testing), "schwab" (live market
    # data), or "replay" (historical CSV backtesting)
    data_feed_provider: str = "simulated"

    # Schwab API
    schwab_client_id: Optional[str] = None
    schwab_client_secret: Optional[str] = None
    schwab_redirect_uri: str = "https://127.0.0.1"
    schwab_tokens_path: str = "schwab_tokens.json"
    schwab_poll_interval_seconds: float = 1.0

    # Replay feed (data_feed_provider="replay") — historical CSV backtesting.
    # speed: 0 = stream as fast as possible, 1.0 = real-time, 2.0 = 2x, etc.
    replay_file_path: str = "data/sample_replay.csv"
    replay_speed: float = 0.0


settings = Settings()
