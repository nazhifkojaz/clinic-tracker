// frontend/src/pages/DashboardRouter.tsx

import { useAuthStore } from "@/stores/authStore";
import StudentDashboard from "./StudentDashboard";
import SupervisorDashboard from "./SupervisorDashboard";

export default function DashboardRouter() {
  const { user } = useAuthStore();

  if (!user) return null;

  if (user.role === "student") {
    return <StudentDashboard />;
  }

  // Supervisors and admins see the supervisor dashboard
  return <SupervisorDashboard />;
}
