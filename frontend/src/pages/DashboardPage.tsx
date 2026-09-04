import { useEffect, useState } from "react";
import type { DashboardStats } from "@/types";
import { dashboardApi } from "@/services/api";

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    dashboardApi
      .stats()
      .then((res) => setStats(res.data))
      .catch(() => setError("Failed to load dashboard stats"));
  }, []);

  if (error) {
    return <p className="text-red-600">{error}</p>;
  }

  if (!stats) {
    return <p className="text-slate-500">Loading dashboard…</p>;
  }

  const cards = [
    { label: "Total Documents", value: stats.total_documents, color: "bg-blue-50 text-blue-700" },
    { label: "Land Records", value: stats.total_land_records, color: "bg-green-50 text-green-700" },
    { label: "Pending", value: stats.documents_pending, color: "bg-yellow-50 text-yellow-700" },
    { label: "Processed", value: stats.documents_processed, color: "bg-emerald-50 text-emerald-700" },
    { label: "Failed", value: stats.documents_failed, color: "bg-red-50 text-red-700" },
    { label: "Reviews", value: stats.pending_reviews, color: "bg-orange-50 text-orange-700" },
  ];

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Dashboard</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {cards.map((c) => (
          <div key={c.label} className={`rounded-xl p-5 ${c.color}`}>
            <p className="text-sm font-medium opacity-80">{c.label}</p>
            <p className="text-3xl font-bold mt-1">{c.value}</p>
          </div>
        ))}
      </div>
      {stats.average_confidence !== null && (
        <div className="mt-6 p-4 bg-white rounded-xl border">
          <p className="text-sm text-slate-500">Average Confidence</p>
          <p className="text-2xl font-bold">
            {(stats.average_confidence * 100).toFixed(1)}%
          </p>
        </div>
      )}
    </div>
  );
}
