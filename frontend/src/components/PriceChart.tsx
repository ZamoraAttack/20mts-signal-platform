import { useEffect, useRef } from "react";
import {
  createChart,
  createSeriesMarkers,
  LineSeries,
  type IChartApi,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type SeriesMarker,
  type Time,
  type UTCTimestamp,
} from "lightweight-charts";
import type { TickPoint } from "../lib/useLiveSocket";

export interface ChartMarker {
  time: number; // unix seconds
  position: "aboveBar" | "belowBar";
  shape: "circle" | "arrowUp" | "arrowDown" | "square";
  color: string;
  text?: string;
}

export function PriceChart({
  data,
  color,
  label,
  symbol,
  markers,
  live = true,
}: {
  data: TickPoint[];
  color: string;
  label: string;
  symbol: string;
  markers?: ChartMarker[];
  live?: boolean;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const seriesMarkersRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: { background: { color: "transparent" }, textColor: "#9ca3af" },
      grid: {
        vertLines: { color: "#1f2028" },
        horzLines: { color: "#1f2028" },
      },
      width: containerRef.current.clientWidth,
      height: 220,
      timeScale: { timeVisible: true, secondsVisible: true },
      rightPriceScale: { borderColor: "#2e303a" },
    });
    const series = chart.addSeries(LineSeries, { color, lineWidth: 2 });

    chartRef.current = chart;
    seriesRef.current = series;
    seriesMarkersRef.current = createSeriesMarkers(series, []);

    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
      seriesMarkersRef.current = null;
    };
  }, [color]);

  useEffect(() => {
    if (!seriesRef.current || data.length === 0) return;
    seriesRef.current.setData(
      data.map((d) => ({ time: d.time as UTCTimestamp, value: d.value }))
    );
    if (live) {
      chartRef.current?.timeScale().scrollToRealTime();
    } else {
      chartRef.current?.timeScale().fitContent();
    }
  }, [data, live]);

  useEffect(() => {
    if (!seriesMarkersRef.current) return;
    const formatted: SeriesMarker<Time>[] = (markers ?? []).map((m) => ({
      time: m.time as UTCTimestamp,
      position: m.position,
      shape: m.shape,
      color: m.color,
      text: m.text,
    }));
    seriesMarkersRef.current.setMarkers(formatted);
  }, [markers]);

  const latest = data[data.length - 1]?.value;

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm font-medium text-gray-300">
          <span className="inline-block h-2 w-2 rounded-full" style={{ background: color }} />
          {label} <span className="text-gray-500">({symbol})</span>
        </div>
        {latest !== undefined && (
          <span className="font-mono text-sm text-gray-200">${latest.toFixed(4)}</span>
        )}
      </div>
      <div ref={containerRef} />
    </div>
  );
}
