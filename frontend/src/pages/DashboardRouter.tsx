// frontend/src/pages/DashboardRouter.tsx

import { lazy, Suspense } from "react";
import { useAuthStore } from "@/stores/authStore";

// Lazy load dashboards separately so recharts only loads for dashboard users
const StudentDashboard = lazy(() => import("./StudentDashboard"));
const SupervisorDashboard = lazy(() => import("./SupervisorDashboard"));

// Simple loading skeleton for dashboards
function DashboardLoading() {
  return (
    <div className="space-y-6 p-6">
      <div className="h-8 w-48 animate-pulse rounded bg-muted" />
      <div className="grid gap-4 md:grid-cols-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-24 animate-pulse rounded-lg bg-muted" />
        ))}
      </div>
      <div className="h-64 animate-pulse rounded-lg bg-muted" />
    </div>
  );
}

export default function DashboardRouter() {
  const { user } = useAuthStore();

  if (!user) return null;

  if (user.role === "student") {
    return (
      <Suspense fallback={<DashboardLoading />}>
        <StudentDashboard />
      </Suspense>
    );
  }

  // Supervisors and admins see the supervisor dashboard
  return (
    <Suspense fallback={<DashboardLoading />}>
      <SupervisorDashboard />
    </Suspense>
  );
}
