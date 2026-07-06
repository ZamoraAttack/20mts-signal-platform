import { useEffect, useRef, useState } from "react";
import type { EngineStatusRead, LiveMessage, SignalEventMsg } from "./types";

export interface TickPoint {
  time: number; // unix seconds
  value: number;
}

export interface LiveData {
  status: EngineStatusRead | null;
  seriesBySymbol: Record<string, TickPoint[]>;
  signalEvents: SignalEventMsg[];
  connected: boolean;
}

const MAX_POINTS = 1800; // 30 minutes at 1s

export function useLiveSocket(): LiveData {
  const [status, setStatus] = useState<EngineStatusRead | null>(null);
  const [seriesBySymbol, setSeriesBySymbol] = useState<Record<string, TickPoint[]>>({});
  const [signalEvents, setSignalEvents] = useState<SignalEventMsg[]>([]);
  const [connected, setConnected] = useState(false);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let ws: WebSocket;
    let cancelled = false;

    const connect = () => {
      const protocol = window.location.protocol === "https:" ? "wss" : "ws";
      ws = new WebSocket(`${protocol}://${window.location.host}/ws/live`);

      ws.onopen = () => setConnected(true);

      ws.onclose = () => {
        setConnected(false);
        if (!cancelled) {
          reconnectTimer.current = setTimeout(connect, 2000);
        }
      };

      ws.onerror = () => ws.close();

      ws.onmessage = (event) => {
        const msg: LiveMessage = JSON.parse(event.data);

        if (msg.type === "tick") {
          setStatus(msg.status);
          const point: TickPoint = {
            time: Math.floor(new Date(msg.timestamp).getTime() / 1000),
            value: msg.price,
          };
          setSeriesBySymbol((prev) => {
            const existing = prev[msg.symbol] ?? [];
            const last = existing[existing.length - 1];
            // lightweight-charts requires strictly increasing/unique timestamps
            const next = last && last.time === point.time
              ? [...existing.slice(0, -1), point]
              : [...existing, point];
            return {
              ...prev,
              [msg.symbol]: next.length > MAX_POINTS ? next.slice(-MAX_POINTS) : next,
            };
          });
        } else if (msg.type === "signal_event") {
          setSignalEvents((prev) => [msg.event, ...prev].slice(0, 50));
        }
      };
    };

    connect();

    return () => {
      cancelled = true;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      ws?.close();
    };
  }, []);

  return { status, seriesBySymbol, signalEvents, connected };
}
