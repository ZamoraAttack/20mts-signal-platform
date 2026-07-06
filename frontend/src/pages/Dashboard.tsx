import { useLiveSocket } from "../lib/useLiveSocket";
import { Card } from "../components/Card";
import { PriceChart } from "../components/PriceChart";
import { StatusPanel } from "../components/StatusPanel";
import { SignalEventFeed } from "../components/SignalEventFeed";
import { WatchlistPanel } from "../components/WatchlistPanel";

export function Dashboard() {
  const { status, seriesBySymbol, signalEvents, connected } = useLiveSocket();

  const symbols = Object.keys(seriesBySymbol);
  const leaderSymbol = symbols.find((s) => s === status?.leader_symbol) ?? symbols[0];
  const stockSymbol = symbols.find((s) => s === status?.stock_symbol) ?? symbols.find((s) => s !== leaderSymbol);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-white">Live Dashboard</h1>
        <p className="text-sm text-gray-500">
          Real-time 1-second price feed and 20 MTS signal state machine.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="flex flex-col gap-6 lg:col-span-2">
          <Card title="Leader">
            {leaderSymbol && seriesBySymbol[leaderSymbol]?.length > 0 ? (
              <PriceChart data={seriesBySymbol[leaderSymbol]} color="#60a5fa" label="Leader" symbol={leaderSymbol} />
            ) : (
              <ChartPlaceholder />
            )}
          </Card>
          <Card title="Stock / Follower">
            {stockSymbol && seriesBySymbol[stockSymbol]?.length > 0 ? (
              <PriceChart data={seriesBySymbol[stockSymbol]} color="#34d399" label="Follower" symbol={stockSymbol} />
            ) : (
              <ChartPlaceholder />
            )}
          </Card>
        </div>

        <div className="flex flex-col gap-6">
          <StatusPanel status={status} connected={connected} />
          <WatchlistPanel />
          <SignalEventFeed events={signalEvents} />
        </div>
      </div>
    </div>
  );
}

function ChartPlaceholder() {
  return (
    <div className="flex h-[220px] items-center justify-center text-sm text-gray-500">
      Waiting for data…
    </div>
  );
}
