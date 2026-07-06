import { Card } from "./Card";
import { formatPercent } from "../lib/format";
import type { DivergenceBucketStats } from "../lib/types";

export function DivergenceBucketTable({ buckets }: { buckets: DivergenceBucketStats[] }) {
  return (
    <Card title="Outcomes by Divergence Duration" className="overflow-x-auto">
      {buckets.length === 0 ? (
        <p className="text-sm text-gray-500">No signals with recorded divergence duration yet.</p>
      ) : (
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-white/10 text-xs uppercase tracking-wide text-gray-500">
              <th className="py-2 pr-4">Duration</th>
              <th className="py-2 pr-4">Signals</th>
              <th className="py-2 pr-4">Win Rate</th>
              <th className="py-2 pr-4">Avg Max Gain %</th>
              <th className="py-2 pr-4">Avg Gain @ 20min %</th>
            </tr>
          </thead>
          <tbody>
            {buckets.map((b) => (
              <tr key={b.bucket} className="border-b border-white/5">
                <td className="py-2 pr-4 font-mono">{b.bucket}</td>
                <td className="py-2 pr-4 font-mono">{b.total_signals}</td>
                <td className="py-2 pr-4 font-mono">{formatPercent(b.win_rate, 0)}</td>
                <td className="py-2 pr-4 font-mono">{b.avg_max_gain_pct?.toFixed(2) ?? "—"}</td>
                <td className="py-2 pr-4 font-mono">{b.avg_gain_at_20min_pct?.toFixed(2) ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  );
}
