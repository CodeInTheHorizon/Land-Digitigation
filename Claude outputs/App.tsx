import { useEffect } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";
import AppLayout from "@/components/layout/AppLayout";
import LoginPage from "@/pages/LoginPage";
import DashboardPage from "@/pages/DashboardPage";
import PlaceholderPage from "@/pages/PlaceholderPage";

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) return <div className="p-8 text-slate-500">Loading…</div>;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  const { loadUser } = useAuth();

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <ProtectedRoute>
            <AppLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route
          path="upload"
          element={
            <PlaceholderPage
              title="Upload Documents"
              description="Drag-and-drop document upload will be implemented in Phase 2."
            />
          }
        />
        <Route
          path="documents"
          element={
            <PlaceholderPage
              title="Documents"
              description="Document listing and management coming in Phase 2."
            />
          }
        />
        <Route
          path="land-records"
          element={
            <PlaceholderPage
              title="Land Records"
              description="Extracted land record browsing coming in Phase 3."
            />
          }
        />
        <Route
          path="review"
          element={
            <PlaceholderPage
              title="Review Queue"
              description="Human review workflow coming in Phase 4."
            />
          }
        />
        <Route
          path="search"
          element={
            <PlaceholderPage
              title="Search"
              description="Full-text and vector search coming in Phase 5."
            />
          }
        />
        <Route
          path="reports"
          element={
            <PlaceholderPage
              title="Reports"
              description="Analytics and reporting coming in Phase 5."
            />
          }
        />
        <Route
          path="settings"
          element={
            <PlaceholderPage
              title="Settings"
              description="System configuration coming in Phase 5."
            />
          }
        />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
