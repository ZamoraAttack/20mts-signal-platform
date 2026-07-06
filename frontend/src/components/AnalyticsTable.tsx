import { Card } from "./Card";
import { formatPercent } from "../lib/format";

export interface AnalyticsRow {
  label: string;
  total_signals: number;
  win_rate: number | null;
  avg_max_gain_pct: number | null;
  avg_gain_at_20min_pct: number | null;
}

export function AnalyticsTable({
  title,
  labelHeader,
  rows,
}: {
  title: string;
  labelHeader: string;
  rows: AnalyticsRow[];
}) {
  return (
    <Card title={title} className="overflow-x-auto">
      {rows.length === 0 ? (
        <p className="text-sm text-gray-500">No signals recorded yet.</p>
      ) : (
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-white/10 text-xs uppercase tracking-wide text-gray-500">
              <th className="py-2 pr-4">{labelHeader}</th>
              <th className="py-2 pr-4">Signals</th>
              <th className="py-2 pr-4">Win Rate</th>
              <th className="py-2 pr-4">Avg Max Gain %</th>
              <th className="py-2 pr-4">Avg Gain @ 20min %</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.label} className="border-b border-white/5">
                <td className="py-2 pr-4 font-mono">{r.label}</td>
                <td className="py-2 pr-4 font-mono">{r.total_signals}</td>
                <td className="py-2 pr-4 font-mono">{formatPercent(r.win_rate, 0)}</td>
                <td className="py-2 pr-4 font-mono">{r.avg_max_gain_pct?.toFixed(2) ?? "—"}</td>
                <td className="py-2 pr-4 font-mono">{r.avg_gain_at_20min_pct?.toFixed(2) ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  );
}
