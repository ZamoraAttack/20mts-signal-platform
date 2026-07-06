import { useEffect, useState } from "react";
import { Card } from "./Card";
import { api } from "../lib/api";
import { formatNumber } from "../lib/format";
import type { WatchlistRead } from "../lib/types";

const SYNC_THRESHOLD = 0.7;

function correlationBadge(value: number | null) {
  if (value === null) {
    return "bg-gray-500/15 text-gray-400 border-gray-500/30";
  }
  if (value >= SYNC_THRESHOLD) {
    return "bg-emerald-500/15 text-emerald-300 border-emerald-500/30";
  }
  if (value >= SYNC_THRESHOLD - 0.15) {
    return "bg-amber-500/15 text-amber-300 border-amber-500/30";
  }
  return "bg-gray-500/15 text-gray-400 border-gray-500/30";
}

export function WatchlistPanel() {
  const [data, setData] = useState<WatchlistRead | null>(null);
  const [editValue, setEditValue] = useState("");
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [promoteError, setPromoteError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const result = await api.getWatchlist();
        if (!cancelled) setData(result);
      } catch {
        // engine not running yet — keep last known state, try again next tick
      }
    };
    poll();
    const interval = setInterval(poll, 3000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  const handlePromote = async (symbol: string) => {
    setBusy(true);
    setPromoteError(null);
    try {
      await api.setActiveStock(symbol);
      const result = await api.getWatchlist();
      setData(result);
    } catch (err) {
      setPromoteError(err instanceof Error ? err.message : "Promotion failed");
    } finally {
      setBusy(false);
    }
  };

  const handleSaveWatchlist = async () => {
    setBusy(true);
    try {
      await api.updateConfig("watchlist_symbols", editValue);
      const result = await api.getWatchlist();
      setData(result);
      setEditing(false);
    } finally {
      setBusy(false);
    }
  };

  const candidates = data ? Object.entries(data.candidates) : [];

  return (
    <Card title="Watchlist">
      {promoteError && (
        <p className="mb-3 rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">
          {promoteError}
        </p>
      )}
      {candidates.length === 0 ? (
        <p className="text-sm text-gray-500">
          No candidates configured. Add comma-separated symbols below.
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          {candidates.map(([symbol, correlation]) => {
            const isActive = symbol === data?.active_symbol;
            return (
              <li
                key={symbol}
                className={`flex items-center justify-between rounded-lg border px-3 py-2 text-sm ${
                  isActive ? "border-violet-500/40 bg-violet-500/5" : "border-white/5 bg-white/[0.02]"
                }`}
              >
                <span className="font-mono text-gray-100">
                  {symbol}
                  {isActive && (
                    <span className="ml-2 rounded-full border border-violet-500/30 bg-violet-500/10 px-2 py-0.5 text-xs text-violet-300">
                      Active
                    </span>
                  )}
                </span>
                <div className="flex items-center gap-3">
                  <span
                    className={`rounded-full border px-2 py-0.5 text-xs font-mono ${correlationBadge(correlation)}`}
                  >
                    {formatNumber(correlation, 3)}
                  </span>
                  {!isActive && (
                    <button
                      onClick={() => handlePromote(symbol)}
                      disabled={busy}
                      className="rounded-md border border-white/10 px-2 py-1 text-xs text-gray-300 hover:bg-white/5 disabled:opacity-50"
                    >
                      Promote
                    </button>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}

      <div className="mt-4 border-t border-white/10 pt-3">
        {editing ? (
          <div className="flex flex-col gap-2">
            <input
              type="text"
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              placeholder="NFLX,HD,LULU,AAPL"
              className="rounded-md border border-white/10 bg-white/[0.02] px-2 py-1 text-sm text-gray-100 font-mono"
            />
            <div className="flex gap-2">
              <button
                onClick={handleSaveWatchlist}
                disabled={busy}
                className="rounded-md border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs text-emerald-300 disabled:opacity-50"
              >
                Save
              </button>
              <button
                onClick={() => setEditing(false)}
                className="rounded-md border border-white/10 px-3 py-1 text-xs text-gray-400"
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <button
            onClick={() => {
              setEditValue(candidates.map(([symbol]) => symbol).join(","));
              setEditing(true);
            }}
            className="text-xs text-gray-500 hover:text-gray-300"
          >
            Edit watchlist
          </button>
        )}
      </div>
    </Card>
  );
}
