import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Card } from "../components/Card";
import { api } from "../lib/api";
import { formatNumber, formatTime, outcomeColor } from "../lib/format";
import type { SignalRead } from "../lib/types";

const OUTCOME_FILTERS = ["all", "pending", "fired", "expired"];

export function Signals() {
  const navigate = useNavigate();
  const [signals, setSignals] = useState<SignalRead[]>([]);
  const [outcomeFilter, setOutcomeFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .listSignals(outcomeFilter === "all" ? undefined : { outcome: outcomeFilter })
      .then((data) => {
        if (!cancelled) {
          setSignals(data);
          setError(null);
        }
      })
      .catch((err) => !cancelled && setError(String(err)))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [outcomeFilter]);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-white">Signals</h1>
        <p className="text-sm text-gray-500">
          Every divergence detected by the engine, with fired/expired outcomes and post-hoc journaling.
        </p>
      </div>

      <div className="flex gap-2">
        {OUTCOME_FILTERS.map((f) => (
          <button
            key={f}
            onClick={() => setOutcomeFilter(f)}
            className={`rounded-full border px-3 py-1 text-xs font-medium capitalize transition-colors ${
              outcomeFilter === f
                ? "border-violet-500/40 bg-violet-500/15 text-violet-300"
                : "border-white/10 text-gray-400 hover:bg-white/5"
            }`}
          >
            {f}
          </button>
        ))}
      </div>

      <Card className="overflow-x-auto">
        {loading ? (
          <p className="text-sm text-gray-500">Loading signals…</p>
        ) : error ? (
          <p className="text-sm text-red-400">{error}</p>
        ) : signals.length === 0 ? (
          <p className="text-sm text-gray-500">No signals recorded yet.</p>
        ) : (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-white/10 text-xs uppercase tracking-wide text-gray-500">
                <th className="py-2 pr-4">Detected</th>
                <th className="py-2 pr-4">Outcome</th>
                <th className="py-2 pr-4">Divergence (s)</th>
                <th className="py-2 pr-4">Correlation</th>
                <th className="py-2 pr-4">Leader @ Divergence</th>
                <th className="py-2 pr-4">Stock @ Divergence</th>
                <th className="py-2 pr-4">High Vol</th>
              </tr>
            </thead>
            <tbody>
              {signals.map((s) => (
                <tr
                  key={s.id}
                  onClick={() => navigate(`/signals/${s.id}`)}
                  className="cursor-pointer border-b border-white/5 transition-colors hover:bg-white/5"
                >
                  <td className="py-2 pr-4 font-mono text-xs">{formatTime(s.divergence_detected_at)}</td>
                  <td className="py-2 pr-4">
                    <span className={`rounded-full border px-2 py-0.5 text-xs font-medium capitalize ${outcomeColor(s.outcome)}`}>
                      {s.outcome ?? "unknown"}
                    </span>
                  </td>
                  <td className="py-2 pr-4 font-mono">{formatNumber(s.divergence_seconds, 1)}</td>
                  <td className="py-2 pr-4 font-mono">{formatNumber(s.correlation_at_signal, 3)}</td>
                  <td className="py-2 pr-4 font-mono">${formatNumber(s.divergence_dia_price)}</td>
                  <td className="py-2 pr-4 font-mono">${formatNumber(s.divergence_stock_price)}</td>
                  <td className="py-2 pr-4">{s.is_high_volatility ? "Yes" : "No"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
