import type { ReactNode } from "react";

export function Card({
  title,
  children,
  className = "",
}: {
  title?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-xl border border-white/10 bg-white/[0.02] p-4 shadow-lg shadow-black/20 ${className}`}
    >
      {title && (
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-400">
          {title}
        </h2>
      )}
      {children}
    </div>
  );
}
