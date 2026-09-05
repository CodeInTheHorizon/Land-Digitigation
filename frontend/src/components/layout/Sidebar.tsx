import { NavLink } from "react-router-dom";
import {
  FileSearch,
  FileText,
  LayoutDashboard,
  Landmark,
  ClipboardCheck,
  BarChart3,
  Settings,
  Upload,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface NavItem {
  label: string;
  to: string;
  icon: LucideIcon;
  end?: boolean;
}

const navItems: NavItem[] = [
  { label: "Dashboard", to: "/", icon: LayoutDashboard, end: true },
  { label: "Upload", to: "/upload", icon: Upload },
  { label: "Documents", to: "/documents", icon: FileText },
  { label: "Land Records", to: "/land-records", icon: Landmark },
  { label: "Review Queue", to: "/review", icon: ClipboardCheck },
  { label: "Search", to: "/search", icon: FileSearch },
  { label: "Reports", to: "/reports", icon: BarChart3 },
  { label: "Settings", to: "/settings", icon: Settings },
];

export default function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <aside className="flex h-full w-64 shrink-0 flex-col border-r border-slate-800 bg-slate-900 text-white">
      <div className="flex items-center gap-3 border-b border-slate-800 px-4 py-4">
        <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary-600" aria-hidden>
          <Landmark size={18} />
        </span>
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold">Land Records</p>
          <p className="truncate text-xs text-slate-400">Digitization System</p>
        </div>
      </div>
      <nav aria-label="Main navigation" className="flex-1 space-y-1 overflow-y-auto p-3">
        {navItems.map(({ label, to, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors duration-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-400",
                isActive ? "bg-primary-600 font-medium text-white" : "text-slate-300 hover:bg-slate-800 hover:text-white",
              )
            }
          >
            <Icon size={17} aria-hidden />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>
      <p className="border-t border-slate-800 px-4 py-3 text-xs text-slate-500">v0.1.0</p>
    </aside>
  );
}
