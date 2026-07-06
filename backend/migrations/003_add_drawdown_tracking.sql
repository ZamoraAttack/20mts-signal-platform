ALTER TABLE signal_outcomes
    ADD COLUMN IF NOT EXISTS price_trough_20min NUMERIC(12,4),
    ADD COLUMN IF NOT EXISTS seconds_to_trough  NUMERIC(8,2),
    ADD COLUMN IF NOT EXISTS max_drawdown_pct   NUMERIC(8,4);
