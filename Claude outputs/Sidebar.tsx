import { NavLink } from "react-router-dom";
import { cn } from "@/lib/utils";

interface NavItem {
  label: string;
  to: string;
  icon: string;
}

const navItems: NavItem[] = [
  { label: "Dashboard", to: "/", icon: "📊" },
  { label: "Upload", to: "/upload", icon: "📤" },
  { label: "Documents", to: "/documents", icon: "📄" },
  { label: "Land Records", to: "/land-records", icon: "🏛️" },
  { label: "Review Queue", to: "/review", icon: "✅" },
  { label: "Search", to: "/search", icon: "🔍" },
  { label: "Reports", to: "/reports", icon: "📈" },
  { label: "Settings", to: "/settings", icon: "⚙️" },
];

export default function Sidebar() {
  return (
    <aside className="w-64 bg-slate-900 text-white min-h-screen flex flex-col">
      <div className="p-4 border-b border-slate-700">
        <h1 className="text-lg font-bold">🏛️ Land Records</h1>
        <p className="text-xs text-slate-400 mt-1">Digitization System</p>
      </div>
      <nav className="flex-1 p-3 space-y-1">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors",
                isActive
                  ? "bg-primary-600 text-white"
                  : "text-slate-300 hover:bg-slate-800 hover:text-white",
              )
            }
          >
            <span>{item.icon}</span>
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>
      <div className="p-4 border-t border-slate-700 text-xs text-slate-500">
        v0.1.0 – Phase 1
      </div>
    </aside>
  );
}
