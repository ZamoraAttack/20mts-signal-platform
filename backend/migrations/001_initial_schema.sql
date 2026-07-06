-- 20 MTS Platform — Initial Schema
-- Run against an empty PostgreSQL database: psql -d twentymts -f 001_initial_schema.sql

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- Trading sessions  (one row per market day)
-- ============================================================
CREATE TABLE IF NOT EXISTS trading_sessions (
    id              VARCHAR(36)  PRIMARY KEY DEFAULT gen_random_uuid()::text,
    session_date    DATE         NOT NULL UNIQUE,
    stock_symbol    VARCHAR(10)  NOT NULL,
    dia_symbol      VARCHAR(10)  NOT NULL DEFAULT 'DIA',
    notes           TEXT,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ============================================================
-- Raw 1-second price ticks
-- ============================================================
CREATE TABLE IF NOT EXISTS price_ticks (
    id          BIGSERIAL    PRIMARY KEY,
    session_id  VARCHAR(36)  REFERENCES trading_sessions(id),
    symbol      VARCHAR(10)  NOT NULL,
    price       NUMERIC(12,4) NOT NULL,
    tick_time   TIMESTAMPTZ  NOT NULL,
    is_high_vol BOOLEAN      NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_price_ticks_symbol_time ON price_ticks (symbol, tick_time DESC);
CREATE INDEX IF NOT EXISTS idx_price_ticks_session     ON price_ticks (session_id);

-- ============================================================
-- Detected signals  (one row per divergence event)
-- ============================================================
CREATE TABLE IF NOT EXISTS signals (
    id                      VARCHAR(36)   PRIMARY KEY DEFAULT gen_random_uuid()::text,
    session_id              VARCHAR(36)   REFERENCES trading_sessions(id),
    stock_symbol            VARCHAR(10)   NOT NULL,

    -- Prices recorded at key moments
    divergence_dia_price    NUMERIC(12,4),
    divergence_stock_price  NUMERIC(12,4),
    signal_dia_price        NUMERIC(12,4),   -- price when reconnection confirmed
    signal_stock_price      NUMERIC(12,4),

    -- Timing
    divergence_detected_at  TIMESTAMPTZ   NOT NULL,
    signal_fired_at         TIMESTAMPTZ,
    expired_at              TIMESTAMPTZ,
    divergence_seconds      NUMERIC(6,2),    -- seconds from divergence → signal/expiry

    -- Metrics at detection
    correlation_at_signal   NUMERIC(6,4),

    -- Outcome: 'pending' | 'fired' | 'expired' | 'filtered'
    outcome                 VARCHAR(20),

    -- Regime context
    is_high_volatility      BOOLEAN       NOT NULL DEFAULT FALSE,
    news_filter_active      BOOLEAN       NOT NULL DEFAULT FALSE,
    u_shape_detected        BOOLEAN       NOT NULL DEFAULT FALSE,

    notes                   TEXT,
    created_at              TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_signals_session  ON signals (session_id);
CREATE INDEX IF NOT EXISTS idx_signals_outcome  ON signals (outcome);
CREATE INDEX IF NOT EXISTS idx_signals_fired_at ON signals (signal_fired_at DESC);

-- ============================================================
-- Signal outcomes  (filled in after the 20-minute window closes)
-- ============================================================
CREATE TABLE IF NOT EXISTS signal_outcomes (
    id                  VARCHAR(36)   PRIMARY KEY DEFAULT gen_random_uuid()::text,
    signal_id           VARCHAR(36)   REFERENCES signals(id) UNIQUE NOT NULL,

    price_at_signal     NUMERIC(12,4) NOT NULL,
    price_peak_20min    NUMERIC(12,4),
    price_at_20min      NUMERIC(12,4),

    max_gain_pct        NUMERIC(8,4),
    gain_at_20min_pct   NUMERIC(8,4),
    seconds_to_peak     NUMERIC(8,2),

    was_successful      BOOLEAN,
    was_red_herring     BOOLEAN       NOT NULL DEFAULT FALSE,

    -- U-shape classification: 'sub_1min' | '1min' | '2min' | '3min' | 'none'
    u_shape_type        VARCHAR(20),

    notes               TEXT,
    recorded_at         TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

-- ============================================================
-- Research journal entries
-- ============================================================
CREATE TABLE IF NOT EXISTS journal_entries (
    id          VARCHAR(36)  PRIMARY KEY DEFAULT gen_random_uuid()::text,
    session_id  VARCHAR(36)  REFERENCES trading_sessions(id),
    signal_id   VARCHAR(36)  REFERENCES signals(id),
    entry_time  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    -- 'observation' | 'note' | 'rule' | 'question'
    entry_type  VARCHAR(20)  NOT NULL,
    body        TEXT         NOT NULL,
    tags        TEXT[]
);

-- ============================================================
-- Strategy configuration  (runtime-editable thresholds)
-- ============================================================
CREATE TABLE IF NOT EXISTS strategy_config (
    key         VARCHAR(100) PRIMARY KEY,
    value       TEXT         NOT NULL,
    description TEXT,
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

INSERT INTO strategy_config (key, value, description) VALUES
    ('sync_window_seconds',              '300',      '5-minute rolling window for correlation'),
    ('sync_correlation_threshold',       '0.70',     'Minimum Pearson correlation for sync regime'),
    ('joint_decline_window_seconds',     '12',       'Seconds over which joint decline is measured'),
    ('joint_decline_min_return',         '-0.0005',  'Required minimum return to confirm decline (-0.05%)'),
    ('ema_period_seconds',               '25',       'EMA period used as short-term trend filter'),
    ('divergence_dia_consecutive_ticks', '3',        'Consecutive DIA up-ticks needed to confirm divergence start'),
    ('divergence_return_window_seconds', '5',        'Return window used as alternative divergence trigger'),
    ('divergence_expiry_seconds',        '120',      'Seconds before an unresolved divergence expires'),
    ('reconnection_consecutive_ticks',   '2',        'Consecutive stock up-ticks needed to confirm reconnection'),
    ('reconnection_lookback_seconds',    '10',       'Lookback window for reconnection price comparison')
ON CONFLICT (key) DO NOTHING;
