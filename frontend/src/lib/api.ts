import type {
  ConfigItem,
  DayAnalytics,
  DivergenceBucketStats,
  EngineStatusRead,
  JournalEntryCreate,
  JournalEntryRead,
  SessionRead,
  SessionStats,
  SignalDetailRead,
  SignalOutcomeRead,
  SignalOutcomeUpsert,
  SignalRead,
  StockAnalytics,
  TimeOfDayAnalytics,
  WatchlistRead,
} from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text();
    let detail = body;
    try {
      const parsed = JSON.parse(body);
      if (typeof parsed.detail === "string") detail = parsed.detail;
    } catch {
      // not JSON — fall back to the raw body text
    }
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  // Status
  getStatus: () => request<EngineStatusRead>("/status"),
  setNewsFilter: (active: boolean) =>
    request<{ active: boolean }>("/status/news-filter", {
      method: "PUT",
      body: JSON.stringify({ active }),
    }),
  getWatchlist: () => request<WatchlistRead>("/status/watchlist"),
  setActiveStock: (symbol: string) =>
    request<EngineStatusRead>("/status/active-stock", {
      method: "PUT",
      body: JSON.stringify({ symbol }),
    }),

  // Sessions
  listSessions: () => request<SessionRead[]>("/sessions"),
  getTodaySession: () => request<SessionRead>("/sessions/today"),
  getSessionStats: (sessionId: string) =>
    request<SessionStats>(`/sessions/${sessionId}/stats`),
  exportSessionUrl: (sessionId: string) => `/api/sessions/${sessionId}/export`,
  getDivergenceBucketStats: (sessionId: string) =>
    request<DivergenceBucketStats[]>(`/sessions/${sessionId}/stats/by-divergence-bucket`),
  getDivergenceBucketStatsAllTime: () =>
    request<DivergenceBucketStats[]>("/signals/stats/by-divergence-bucket"),

  // Signals
  listSignals: (params?: { session_id?: string; outcome?: string }) => {
    const qs = new URLSearchParams();
    if (params?.session_id) qs.set("session_id", params.session_id);
    if (params?.outcome) qs.set("outcome", params.outcome);
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return request<SignalRead[]>(`/signals${suffix}`);
  },
  getSignal: (id: string) => request<SignalRead>(`/signals/${id}`),
  getSignalDetail: (id: string) => request<SignalDetailRead>(`/signals/${id}/detail`),
  getSignalOutcome: (id: string) =>
    request<SignalOutcomeRead>(`/signals/${id}/outcome`),
  upsertSignalOutcome: (id: string, payload: SignalOutcomeUpsert) =>
    request<SignalOutcomeRead>(`/signals/${id}/outcome`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),

  // Journal
  listJournal: (params?: { session_id?: string; signal_id?: string }) => {
    const qs = new URLSearchParams();
    if (params?.session_id) qs.set("session_id", params.session_id);
    if (params?.signal_id) qs.set("signal_id", params.signal_id);
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return request<JournalEntryRead[]>(`/journal${suffix}`);
  },
  createJournalEntry: (payload: JournalEntryCreate) =>
    request<JournalEntryRead>("/journal", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // Config
  listConfig: () => request<ConfigItem[]>("/config"),
  updateConfig: (key: string, value: string) =>
    request<ConfigItem>(`/config/${key}`, {
      method: "PUT",
      body: JSON.stringify({ value }),
    }),

  // Analytics
  getAnalyticsByStock: () => request<StockAnalytics[]>("/analytics/by-stock"),
  getAnalyticsByDay: () => request<DayAnalytics[]>("/analytics/by-day"),
  getAnalyticsByTimeOfDay: () => request<TimeOfDayAnalytics[]>("/analytics/by-time-of-day"),
};
