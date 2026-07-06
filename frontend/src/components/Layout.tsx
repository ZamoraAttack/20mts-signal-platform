import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";

const navItems = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/signals", label: "Signals" },
  { to: "/research", label: "Research" },
  { to: "/journal", label: "Journal" },
  { to: "/sessions", label: "Sessions" },
];

export function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen bg-[#0b0e14] text-gray-200">
      <aside className="w-56 shrink-0 border-r border-white/10 bg-gradient-to-b from-[#11141d] to-[#0b0e14] p-4">
        <div className="mb-8 px-2">
          <h1 className="text-lg font-semibold tracking-tight text-white">20 MTS</h1>
          <p className="text-xs text-gray-500">Signal Research Platform</p>
        </div>
        <nav className="flex flex-col gap-1">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-violet-500/15 text-violet-300 border border-violet-500/30"
                    : "text-gray-400 hover:bg-white/5 hover:text-gray-200 border border-transparent"
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="flex-1 overflow-y-auto p-6">{children}</main>
    </div>
  );
}
