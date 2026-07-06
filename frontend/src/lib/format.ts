export const STATE_LABELS: Record<string, string> = {
  idle: "Idle",
  monitoring: "Monitoring",
  joint_decline: "Joint Decline",
  divergence: "Divergence",
  signal_fired: "Signal Fired",
  signal_expired: "Signal Expired",
  cooldown: "Cooldown",
};

export const STATE_COLORS: Record<string, string> = {
  idle: "bg-gray-500/15 text-gray-400 border-gray-500/30",
  monitoring: "bg-blue-500/15 text-blue-300 border-blue-500/30",
  joint_decline: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  divergence: "bg-orange-500/15 text-orange-300 border-orange-500/30",
  signal_fired: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  signal_expired: "bg-red-500/15 text-red-300 border-red-500/30",
  cooldown: "bg-violet-500/15 text-violet-300 border-violet-500/30",
};

export function stateLabel(state: string): string {
  return STATE_LABELS[state] ?? state;
}

export function stateColor(state: string): string {
  return STATE_COLORS[state] ?? STATE_COLORS.idle;
}

export function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour12: false });
}

export function formatPercent(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined) return "—";
  return `${(value * 100).toFixed(digits)}%`;
}

export function formatNumber(value: number | null | undefined, digits = 4): string {
  if (value === null || value === undefined) return "—";
  return value.toFixed(digits);
}

export function outcomeColor(outcome: string | null): string {
  switch (outcome) {
    case "fired":
      return "bg-emerald-500/15 text-emerald-300 border-emerald-500/30";
    case "expired":
      return "bg-red-500/15 text-red-300 border-red-500/30";
    case "pending":
      return "bg-blue-500/15 text-blue-300 border-blue-500/30";
    default:
      return "bg-gray-500/15 text-gray-400 border-gray-500/30";
  }
}
