export interface SignalRead {
  id: string;
  session_id: string | null;
  stock_symbol: string;

  divergence_dia_price: number | null;
  divergence_stock_price: number | null;
  signal_dia_price: number | null;
  signal_stock_price: number | null;

  divergence_detected_at: string;
  signal_fired_at: string | null;
  expired_at: string | null;
  divergence_seconds: number | null;

  correlation_at_signal: number | null;
  outcome: string | null;

  is_high_volatility: boolean;
  news_filter_active: boolean;
  u_shape_detected: boolean;

  notes: string | null;
  created_at: string;
}

export interface SignalOutcomeUpsert {
  price_at_signal?: number | null;
  price_peak_20min?: number | null;
  price_at_20min?: number | null;
  max_gain_pct?: number | null;
  gain_at_20min_pct?: number | null;
  seconds_to_peak?: number | null;
  price_trough_20min?: number | null;
  seconds_to_trough?: number | null;
  max_drawdown_pct?: number | null;
  was_successful?: boolean | null;
  was_red_herring?: boolean;
  u_shape_type?: string | null;
  notes?: string | null;
}

export interface SignalOutcomeRead extends SignalOutcomeUpsert {
  id: string;
  signal_id: string;
  recorded_at: string;
}

export interface SignalTickPoint {
  symbol: string;
  tick_time: string;
  price: number;
}

export interface SignalSuggestionRead {
  profitable_at_20min: boolean | null;
  hit_target: boolean | null;
  suggested_was_red_herring: boolean | null;
  suggested_u_shape_type: string | null;
  classification: "likely_success" | "likely_failure" | "needs_review" | null;
  notes: string;
}

export interface SignalDetailRead {
  signal: SignalRead;
  outcome: SignalOutcomeRead | null;
  leader_symbol: string;
  ticks: SignalTickPoint[];
  suggestion: SignalSuggestionRead;
}

export interface JournalEntryCreate {
  session_id?: string | null;
  signal_id?: string | null;
  entry_type: string;
  body: string;
}

export interface JournalEntryRead extends JournalEntryCreate {
  id: string;
  entry_time: string;
}

export interface ConfigItem {
  key: string;
  value: string;
  description: string | null;
}

export interface SessionRead {
  id: string;
  session_date: string;
  stock_symbol: string;
  dia_symbol: string;
  notes: string | null;
  created_at: string;
}

export interface SessionStats {
  session_id: string;
  session_date: string;
  total_signals: number;
  fired: number;
  expired: number;
  win_rate: number | null;
  avg_divergence_seconds: number | null;
}

export interface EngineStatusRead {
  state: string;
  correlation: number | null;
  is_synchronized: boolean;
  dia_price: number | null;
  stock_price: number | null;
  leader_symbol: string;
  stock_symbol: string;
  tick_count: number;
  active_signal_id: string | null;
  divergence_start_time: string | null;
  news_filter_active: boolean;
  data_feed_provider: string;
}

export interface DivergenceBucketStats {
  bucket: string;
  total_signals: number;
  wins: number;
  decided: number;
  win_rate: number | null;
  avg_max_gain_pct: number | null;
  avg_gain_at_20min_pct: number | null;
}

export interface StockAnalytics {
  stock_symbol: string;
  total_signals: number;
  wins: number;
  decided: number;
  win_rate: number | null;
  avg_max_gain_pct: number | null;
  avg_gain_at_20min_pct: number | null;
}

export interface DayAnalytics {
  session_date: string;
  total_signals: number;
  wins: number;
  decided: number;
  win_rate: number | null;
  avg_max_gain_pct: number | null;
  avg_gain_at_20min_pct: number | null;
}

export interface TimeOfDayAnalytics {
  hour_bucket: string;
  total_signals: number;
  wins: number;
  decided: number;
  win_rate: number | null;
  avg_max_gain_pct: number | null;
  avg_gain_at_20min_pct: number | null;
}

export interface WatchlistRead {
  leader_symbol: string;
  active_symbol: string;
  candidates: Record<string, number | null>;
}

export interface SignalEventMsg {
  signal_id: string;
  state: string;
  timestamp: string;
  dia_price: number;
  stock_price: number;
  correlation: number | null;
  divergence_seconds_elapsed: number | null;
  notes: string;
}

export type LiveMessage =
  | {
      type: "tick";
      symbol: string;
      price: number;
      timestamp: string;
      status: EngineStatusRead;
    }
  | {
      type: "signal_event";
      event: SignalEventMsg;
    };
