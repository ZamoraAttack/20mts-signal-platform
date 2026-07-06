import { useEffect, useState } from "react";
import { Card } from "../components/Card";
import { DivergenceBucketTable } from "../components/DivergenceBucketTable";
import { api } from "../lib/api";
import { formatPercent } from "../lib/format";
import type { DivergenceBucketStats, SessionRead, SessionStats } from "../lib/types";

export function Sessions() {
  const [sessions, setSessions] = useState<SessionRead[]>([]);
  const [stats, setStats] = useState<Record<string, SessionStats>>({});
  const [loading, setLoading] = useState(true);
  const [buckets, setBuckets] = useState<DivergenceBucketStats[]>([]);

  useEffect(() => {
    api.getDivergenceBucketStatsAllTime().then(setBuckets).catch(() => setBuckets([]));
  }, []);

  useEffect(() => {
    let cancelled = false;
    api
      .listSessions()
      .then(async (data) => {
        if (cancelled) return;
        setSessions(data);
        const entries = await Promise.all(
          data.map(async (s) => {
            try {
              return [s.id, await api.getSessionStats(s.id)] as const;
            } catch {
              return null;
            }
          })
        );
        if (!cancelled) {
          const map: Record<string, SessionStats> = {};
          for (const entry of entries) {
            if (entry) map[entry[0]] = entry[1];
          }
          setStats(map);
        }
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-white">Sessions</h1>
        <p className="text-sm text-gray-500">
          One row per trading day, with signal counts and win-rate stats.
        </p>
      </div>

      <Card className="overflow-x-auto">
        {loading ? (
          <p className="text-sm text-gray-500">Loading sessions…</p>
        ) : sessions.length === 0 ? (
          <p className="text-sm text-gray-500">No sessions recorded yet.</p>
        ) : (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-white/10 text-xs uppercase tracking-wide text-gray-500">
                <th className="py-2 pr-4">Date</th>
                <th className="py-2 pr-4">Stock</th>
                <th className="py-2 pr-4">Total Signals</th>
                <th className="py-2 pr-4">Fired</th>
                <th className="py-2 pr-4">Expired</th>
                <th className="py-2 pr-4">Win Rate</th>
                <th className="py-2 pr-4">Avg Divergence (s)</th>
                <th className="py-2 pr-4"></th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((s) => {
                const stat = stats[s.id];
                return (
                  <tr key={s.id} className="border-b border-white/5">
                    <td className="py-2 pr-4 font-mono">{s.session_date}</td>
                    <td className="py-2 pr-4">
                      {s.stock_symbol} <span className="text-gray-500">vs {s.dia_symbol}</span>
                    </td>
                    <td className="py-2 pr-4 font-mono">{stat?.total_signals ?? "—"}</td>
                    <td className="py-2 pr-4 font-mono">{stat?.fired ?? "—"}</td>
                    <td className="py-2 pr-4 font-mono">{stat?.expired ?? "—"}</td>
                    <td className="py-2 pr-4 font-mono">{formatPercent(stat?.win_rate, 0)}</td>
                    <td className="py-2 pr-4 font-mono">
                      {stat?.avg_divergence_seconds?.toFixed(1) ?? "—"}
                    </td>
                    <td className="py-2 pr-4">
                      <a
                        href={api.exportSessionUrl(s.id)}
                        download
                        className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-xs font-medium text-emerald-300 hover:bg-emerald-500/20"
                      >
                        Export CSV
                      </a>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </Card>

      <DivergenceBucketTable buckets={buckets} />
    </div>
  );
}
