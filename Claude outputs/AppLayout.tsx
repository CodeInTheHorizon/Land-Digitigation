import { Outlet } from "react-router-dom";
import Sidebar from "./Sidebar";
import { useAuth } from "@/hooks/useAuth";

export default function AppLayout() {
  const { user, logout } = useAuth();

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col">
        {/* Top bar */}
        <header className="h-14 border-b border-slate-200 flex items-center justify-between px-6 bg-white">
          <span className="text-sm text-slate-500">
            Intelligent Land Record Digitization
          </span>
          <div className="flex items-center gap-4 text-sm">
            <span className="text-slate-600">{user?.full_name ?? user?.email}</span>
            <button
              onClick={logout}
              className="text-red-500 hover:text-red-700 transition-colors"
            >
              Logout
            </button>
          </div>
        </header>
        {/* Page content */}
        <main className="flex-1 p-6 bg-slate-50 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
