import { useEffect, useState } from "react";
import { AnalyticsTable, type AnalyticsRow } from "../components/AnalyticsTable";
import { DivergenceBucketTable } from "../components/DivergenceBucketTable";
import { api } from "../lib/api";
import type { DayAnalytics, DivergenceBucketStats, StockAnalytics, TimeOfDayAnalytics } from "../lib/types";

export function Research() {
  const [byStock, setByStock] = useState<StockAnalytics[]>([]);
  const [byDay, setByDay] = useState<DayAnalytics[]>([]);
  const [byTimeOfDay, setByTimeOfDay] = useState<TimeOfDayAnalytics[]>([]);
  const [byBucket, setByBucket] = useState<DivergenceBucketStats[]>([]);

  useEffect(() => {
    api.getAnalyticsByStock().then(setByStock).catch(() => setByStock([]));
    api.getAnalyticsByDay().then(setByDay).catch(() => setByDay([]));
    api.getAnalyticsByTimeOfDay().then(setByTimeOfDay).catch(() => setByTimeOfDay([]));
    api.getDivergenceBucketStatsAllTime().then(setByBucket).catch(() => setByBucket([]));
  }, []);

  const stockRows: AnalyticsRow[] = byStock.map((r) => ({
    label: r.stock_symbol,
    total_signals: r.total_signals,
    win_rate: r.win_rate,
    avg_max_gain_pct: r.avg_max_gain_pct,
    avg_gain_at_20min_pct: r.avg_gain_at_20min_pct,
  }));

  const dayRows: AnalyticsRow[] = byDay.map((r) => ({
    label: r.session_date,
    total_signals: r.total_signals,
    win_rate: r.win_rate,
    avg_max_gain_pct: r.avg_max_gain_pct,
    avg_gain_at_20min_pct: r.avg_gain_at_20min_pct,
  }));

  const timeOfDayRows: AnalyticsRow[] = byTimeOfDay.map((r) => ({
    label: r.hour_bucket,
    total_signals: r.total_signals,
    win_rate: r.win_rate,
    avg_max_gain_pct: r.avg_max_gain_pct,
    avg_gain_at_20min_pct: r.avg_gain_at_20min_pct,
  }));

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-white">Research</h1>
        <p className="text-sm text-gray-500">
          "Compared to what" — baselines across every signal recorded so far, broken down a few different ways.
        </p>
      </div>

      <AnalyticsTable title="By Stock" labelHeader="Stock" rows={stockRows} />
      <DivergenceBucketTable buckets={byBucket} />
      <AnalyticsTable title="By Time of Day (ET)" labelHeader="Hour" rows={timeOfDayRows} />
      <AnalyticsTable title="By Day" labelHeader="Date" rows={dayRows} />
    </div>
  );
}
