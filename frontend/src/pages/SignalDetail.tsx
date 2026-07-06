import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Card } from "../components/Card";
import { PriceChart, type ChartMarker } from "../components/PriceChart";
import { SignalOutcomeForm } from "../components/SignalOutcomeForm";
import { api } from "../lib/api";
import { formatNumber, formatTime, outcomeColor } from "../lib/format";
import type { SignalDetailRead } from "../lib/types";
import type { TickPoint } from "../lib/useLiveSocket";

function toSeries(detail: SignalDetailRead, symbol: string): TickPoint[] {
  return detail.ticks
    .filter((t) => t.symbol === symbol)
    .map((t) => ({ time: Math.floor(new Date(t.tick_time).getTime() / 1000), value: t.price }));
}

function toUnixSeconds(iso: string): number {
  return Math.floor(new Date(iso).getTime() / 1000);
}

/** Divergence/signal/expired markers apply to both charts; peak/trough are stock-only. */
function computeMarkers(detail: SignalDetailRead, isStockChart: boolean): ChartMarker[] {
  const { signal, outcome } = detail;
  const markers: ChartMarker[] = [
    {
      time: toUnixSeconds(signal.divergence_detected_at),
      position: "belowBar",
      shape: "arrowDown",
      color: "#9ca3af",
      text: "Divergence",
    },
  ];

  if (signal.signal_fired_at) {
    markers.push({
      time: toUnixSeconds(signal.signal_fired_at),
      position: "aboveBar",
      shape: "arrowUp",
      color: "#a78bfa",
      text: "Signal",
    });

    if (isStockChart && outcome) {
      const firedAt = toUnixSeconds(signal.signal_fired_at);
      if (outcome.seconds_to_peak != null) {
        markers.push({
          time: firedAt + Math.round(outcome.seconds_to_peak),
          position: "aboveBar",
          shape: "circle",
          color: "#34d399",
          text: "Peak",
        });
      }
      if (outcome.seconds_to_trough != null) {
        markers.push({
          time: firedAt + Math.round(outcome.seconds_to_trough),
          position: "belowBar",
          shape: "circle",
          color: "#f87171",
          text: "Trough",
        });
      }
    }
  } else if (signal.expired_at) {
    markers.push({
      time: toUnixSeconds(signal.expired_at),
      position: "aboveBar",
      shape: "square",
      color: "#f87171",
      text: "Expired",
    });
  }

  return markers.sort((a, b) => a.time - b.time);
}

function YesNoBadge({ value }: { value: boolean | null }) {
  const label = value === null ? "Unknown" : value ? "Yes" : "No";
  const color =
    value === null
      ? "bg-gray-500/15 text-gray-400 border-gray-500/30"
      : value
        ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/30"
        : "bg-red-500/15 text-red-300 border-red-500/30";
  return <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${color}`}>{label}</span>;
}

const CLASSIFICATION_LABELS: Record<string, string> = {
  likely_success: "Likely Success",
  likely_failure: "Likely Failure",
  needs_review: "Needs Review",
};

const CLASSIFICATION_COLORS: Record<string, string> = {
  likely_success: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  likely_failure: "bg-red-500/15 text-red-300 border-red-500/30",
  needs_review: "bg-amber-500/15 text-amber-300 border-amber-500/30",
};

function ClassificationBadge({ classification }: { classification: string | null }) {
  if (!classification) {
    return (
      <span className="rounded-full border border-gray-500/30 bg-gray-500/15 px-3 py-1 text-sm font-medium text-gray-400">
        Not yet tracked
      </span>
    );
  }
  return (
    <span className={`rounded-full border px-3 py-1 text-sm font-semibold ${CLASSIFICATION_COLORS[classification]}`}>
      {CLASSIFICATION_LABELS[classification] ?? classification}
    </span>
  );
}

export function SignalDetail() {
  const { id } = useParams<{ id: string }>();
  const [detail, setDetail] = useState<SignalDetailRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    setLoading(true);
    api
      .getSignalDetail(id)
      .then((data) => !cancelled && setDetail(data))
      .catch((err) => !cancelled && setError(err instanceof Error ? err.message : String(err)))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (loading) return <p className="text-sm text-gray-500">Loading signal…</p>;
  if (error) return <p className="text-sm text-red-400">{error}</p>;
  if (!detail) return null;

  const { signal, outcome, suggestion, leader_symbol } = detail;
  const leaderSeries = toSeries(detail, leader_symbol);
  const stockSeries = toSeries(detail, signal.stock_symbol);
  const entryPrice = outcome?.price_at_signal ?? signal.signal_stock_price ?? signal.divergence_stock_price;
  const leaderMarkers = computeMarkers(detail, false);
  const stockMarkers = computeMarkers(detail, true);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link to="/signals" className="text-xs text-gray-500 hover:text-gray-300">
          ← Back to Signals
        </Link>
        <div className="mt-1 flex items-center gap-3">
          <h1 className="text-xl font-semibold text-white">Signal {signal.id.slice(0, 8)}</h1>
          <span className={`rounded-full border px-2 py-0.5 text-xs font-medium capitalize ${outcomeColor(signal.outcome)}`}>
            {signal.outcome ?? "unknown"}
          </span>
        </div>
        <p className="text-sm text-gray-500">
          {signal.stock_symbol} vs {leader_symbol} — detected {formatTime(signal.divergence_detected_at)}
        </p>
      </div>

      <Card title="Metrics">
        <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm sm:grid-cols-4">
          <Metric label="Entry Price" value={entryPrice != null ? `$${formatNumber(entryPrice)}` : "—"} />
          <Metric label="Peak Price" value={outcome?.price_peak_20min != null ? `$${formatNumber(outcome.price_peak_20min)}` : "—"} />
          <Metric label="Price @ 20min" value={outcome?.price_at_20min != null ? `$${formatNumber(outcome.price_at_20min)}` : "—"} />
          <Metric label="Max Gain %" value={outcome?.max_gain_pct != null ? `${formatNumber(outcome.max_gain_pct, 2)}%` : "—"} />
          <Metric label="Gain @ 20min %" value={outcome?.gain_at_20min_pct != null ? `${formatNumber(outcome.gain_at_20min_pct, 2)}%` : "—"} />
          <Metric label="Seconds to Peak" value={outcome?.seconds_to_peak != null ? formatNumber(outcome.seconds_to_peak, 0) : "—"} />
          <Metric label="Max Drawdown %" value={outcome?.max_drawdown_pct != null ? `${formatNumber(outcome.max_drawdown_pct, 2)}%` : "—"} />
          <Metric label="Seconds to Trough" value={outcome?.seconds_to_trough != null ? formatNumber(outcome.seconds_to_trough, 0) : "—"} />
          <Metric label="Divergence Duration" value={signal.divergence_seconds != null ? `${formatNumber(signal.divergence_seconds, 1)}s` : "—"} />
          <Metric label="Correlation" value={formatNumber(signal.correlation_at_signal, 3)} />
        </dl>
      </Card>

      <Card title="Suggested Classification (not saved — for your review)">
        <ClassificationBadge classification={suggestion.classification} />
        <div className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 text-sm sm:grid-cols-4">
          <div>
            <dt className="text-gray-500">Profitable @ 20min</dt>
            <dd className="mt-1"><YesNoBadge value={suggestion.profitable_at_20min} /></dd>
          </div>
          <div>
            <dt className="text-gray-500">Hit 3% Target</dt>
            <dd className="mt-1"><YesNoBadge value={suggestion.hit_target} /></dd>
          </div>
          <div>
            <dt className="text-gray-500">Suggested Red Herring</dt>
            <dd className="mt-1"><YesNoBadge value={suggestion.suggested_was_red_herring} /></dd>
          </div>
          <div>
            <dt className="text-gray-500">Suggested U-Shape</dt>
            <dd className="mt-1 text-gray-200">{suggestion.suggested_u_shape_type ?? "—"}</dd>
          </div>
        </div>
        <p className="mt-3 text-xs text-gray-500">{suggestion.notes}</p>
      </Card>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card title="Leader (window)">
          {leaderSeries.length > 0 ? (
            <PriceChart data={leaderSeries} color="#60a5fa" label="Leader" symbol={leader_symbol} markers={leaderMarkers} live={false} />
          ) : (
            <p className="text-sm text-gray-500">No ticks recorded in this window.</p>
          )}
        </Card>
        <Card title="Stock (window)">
          {stockSeries.length > 0 ? (
            <PriceChart data={stockSeries} color="#34d399" label="Stock" symbol={signal.stock_symbol} markers={stockMarkers} live={false} />
          ) : (
            <p className="text-sm text-gray-500">No ticks recorded in this window.</p>
          )}
        </Card>
      </div>

      <Card title="Outcome">
        <SignalOutcomeForm signal={signal} suggestion={suggestion} />
      </Card>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-gray-500">{label}</dt>
      <dd className="font-mono text-gray-100">{value}</dd>
    </div>
  );
}
