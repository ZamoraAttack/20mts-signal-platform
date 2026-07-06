import { useState } from "react";
import { Card } from "./Card";
import { api } from "../lib/api";
import { formatNumber, stateColor, stateLabel } from "../lib/format";
import type { EngineStatusRead } from "../lib/types";

export function StatusPanel({
  status,
  connected,
}: {
  status: EngineStatusRead | null;
  connected: boolean;
}) {
  const [toggling, setToggling] = useState(false);

  const handleToggleNewsFilter = async () => {
    if (!status) return;
    setToggling(true);
    try {
      await api.setNewsFilter(!status.news_filter_active);
    } finally {
      setToggling(false);
    }
  };

  return (
    <Card title="Engine Status">
      <div className="flex flex-wrap items-center gap-3">
        <span
          className={`rounded-full border px-3 py-1 text-sm font-semibold ${
            status ? stateColor(status.state) : stateColor("idle")
          }`}
        >
          {status ? stateLabel(status.state) : "Connecting…"}
        </span>
        <span
          className={`rounded-full border px-2 py-0.5 text-xs font-medium ${
            connected
              ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
              : "border-red-500/30 bg-red-500/10 text-red-300"
          }`}
        >
          {connected ? "Live" : "Disconnected"}
        </span>
        {status?.data_feed_provider === "replay" && (
          <span className="rounded-full border border-violet-500/30 bg-violet-500/10 px-2 py-0.5 text-xs font-medium text-violet-300">
            Replay
          </span>
        )}
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 text-sm sm:grid-cols-3">
        <div>
          <dt className="text-gray-500">Correlation</dt>
          <dd className="font-mono text-gray-100">{formatNumber(status?.correlation, 4)}</dd>
        </div>
        <div>
          <dt className="text-gray-500">Synchronized</dt>
          <dd className="text-gray-100">{status?.is_synchronized ? "Yes" : "No"}</dd>
        </div>
        <div>
          <dt className="text-gray-500">Tick Count</dt>
          <dd className="font-mono text-gray-100">{status?.tick_count ?? "—"}</dd>
        </div>
        <div>
          <dt className="text-gray-500">Leader Price</dt>
          <dd className="font-mono text-gray-100">
            {status?.dia_price ? `$${formatNumber(status.dia_price)}` : "—"}
          </dd>
        </div>
        <div>
          <dt className="text-gray-500">Stock Price</dt>
          <dd className="font-mono text-gray-100">
            {status?.stock_price ? `$${formatNumber(status.stock_price)}` : "—"}
          </dd>
        </div>
        <div>
          <dt className="text-gray-500">Active Signal</dt>
          <dd className="truncate font-mono text-xs text-gray-100">
            {status?.active_signal_id ?? "—"}
          </dd>
        </div>
        {status?.divergence_start_time && (
          <div className="col-span-2 sm:col-span-3">
            <dt className="text-gray-500">Divergence Started</dt>
            <dd className="font-mono text-gray-100">
              {new Date(status.divergence_start_time).toLocaleTimeString([], { hour12: false })}
              {" — "}
              {Math.max(0, Math.floor((Date.now() - new Date(status.divergence_start_time).getTime()) / 1000))}s ago
            </dd>
          </div>
        )}
      </dl>

      <div className="mt-4 flex items-center justify-between border-t border-white/10 pt-4">
        <div>
          <p className="text-sm font-medium text-gray-200">News Filter</p>
          <p className="text-xs text-gray-500">Manually block new signals during news events</p>
        </div>
        <button
          onClick={handleToggleNewsFilter}
          disabled={!status || toggling}
          className={`relative h-6 w-11 rounded-full transition-colors disabled:opacity-50 ${
            status?.news_filter_active ? "bg-amber-500" : "bg-gray-600"
          }`}
        >
          <span
            className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition-transform ${
              status?.news_filter_active ? "translate-x-5" : "translate-x-0.5"
            }`}
          />
        </button>
      </div>
    </Card>
  );
}
