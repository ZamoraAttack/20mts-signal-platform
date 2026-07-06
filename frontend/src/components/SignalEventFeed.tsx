import { Card } from "./Card";
import { formatNumber, formatTime, stateColor, stateLabel } from "../lib/format";
import type { SignalEventMsg } from "../lib/types";

export function SignalEventFeed({ events }: { events: SignalEventMsg[] }) {
  return (
    <Card title="Live Signal Events">
      {events.length === 0 ? (
        <p className="text-sm text-gray-500">
          No signal events yet this session. Events appear here as the engine
          detects divergence, fires, or expires a setup.
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          {events.map((event, i) => (
            <li
              key={`${event.signal_id}-${event.state}-${i}`}
              className="rounded-lg border border-white/10 bg-white/[0.02] p-3 text-sm"
            >
              <div className="flex items-center justify-between gap-2">
                <span className={`rounded-full border px-2 py-0.5 text-xs font-semibold ${stateColor(event.state)}`}>
                  {stateLabel(event.state)}
                </span>
                <span className="font-mono text-xs text-gray-500">{formatTime(event.timestamp)}</span>
              </div>
              <p className="mt-2 text-gray-300">{event.notes}</p>
              <div className="mt-2 grid grid-cols-3 gap-2 font-mono text-xs text-gray-400">
                <span>Leader ${formatNumber(event.dia_price)}</span>
                <span>Stock ${formatNumber(event.stock_price)}</span>
                <span>Corr {formatNumber(event.correlation, 3)}</span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
