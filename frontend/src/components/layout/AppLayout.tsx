import { useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { LogOut, Menu, X } from "lucide-react";
import Sidebar from "./Sidebar";
import { useAuth } from "@/hooks/useAuth";

export default function AppLayout() {
  const { user, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const { pathname } = useLocation();

  useEffect(() => setMenuOpen(false), [pathname]);

  const initials = (user?.full_name ?? user?.email ?? "?").trim().charAt(0).toUpperCase();

  return (
    <div className="flex min-h-screen bg-slate-50">
      <div className="hidden lg:block">
        <Sidebar />
      </div>

      {menuOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-slate-900/50" onClick={() => setMenuOpen(false)} aria-hidden />
          <div className="absolute inset-y-0 left-0">
            <Sidebar onNavigate={() => setMenuOpen(false)} />
          </div>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center justify-between gap-3 border-b border-slate-200 bg-white px-4 sm:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <button
              type="button"
              onClick={() => setMenuOpen((open) => !open)}
              aria-label={menuOpen ? "Close navigation menu" : "Open navigation menu"}
              aria-expanded={menuOpen}
              className="rounded-lg p-2 text-slate-600 transition-colors duration-200 hover:bg-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600 lg:hidden"
            >
              {menuOpen ? <X size={18} /> : <Menu size={18} />}
            </button>
            <span className="truncate text-sm font-medium text-slate-700">
              Intelligent Land Record Digitization
            </span>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden min-w-0 text-right sm:block">
              <p className="truncate text-sm font-medium text-slate-800">{user?.full_name ?? user?.email ?? "Signed in"}</p>
              <p className="truncate text-xs text-slate-500">{user?.is_superuser ? "Administrator" : "Operator"}</p>
            </div>
            <span aria-hidden className="flex h-8 w-8 items-center justify-center rounded-full bg-primary-50 text-sm font-semibold text-primary-700">
              {initials}
            </span>
            <button
              onClick={logout}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-700 transition-colors duration-200 hover:bg-slate-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600"
            >
              <LogOut size={15} aria-hidden />
              <span className="hidden sm:inline">Logout</span>
            </button>
          </div>
        </header>

        <main className="flex-1 overflow-x-hidden p-4 sm:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
