INSERT INTO strategy_config (key, value, description) VALUES
    ('watchlist_symbols', '', 'Comma-separated candidate stocks passively screened for correlation vs leader_symbol')
ON CONFLICT (key) DO NOTHING;
