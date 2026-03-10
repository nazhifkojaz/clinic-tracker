import { useEffect } from "react";
import { Routes, Route } from "react-router-dom";
import { useAuthStore } from "@/stores/authStore";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { Toaster } from "@/components/ui/sonner";
import ProtectedRoute from "@/components/layout/ProtectedRoute";
import AppLayout from "@/components/layout/AppLayout";
import Login from "@/pages/Login";
import DashboardRouter from "@/pages/DashboardRouter";
import CaseInputForm from "@/pages/CaseInputForm";
import SubmissionHistory from "@/pages/SubmissionHistory";
import SendNotification from "@/pages/SendNotification";
import NotificationHistory from "@/pages/NotificationHistory";
import UserManagement from "@/pages/admin/UserManagement";
import DepartmentManagement from "@/pages/admin/DepartmentManagement";
import AssignmentManagement from "@/pages/admin/AssignmentManagement";
import AuditLog from "@/pages/admin/AuditLog";
import NotFound from "@/pages/NotFound";

function App() {
  const { initialize, isInitialized } = useAuthStore();

  useEffect(() => {
    initialize();
  }, [initialize]);

  if (!isInitialized) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-muted-foreground">Loading...</p>
      </div>
    );
  }

  return (
    <ErrorBoundary>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<AppLayout />}>
            <Route path="/" element={<DashboardRouter />} />
            <Route path="/cases/new" element={<CaseInputForm />} />
            <Route path="/submissions" element={<SubmissionHistory />} />
            <Route path="/notifications/send" element={<SendNotification />} />
            <Route path="/notifications" element={<NotificationHistory />} />
            <Route element={<ProtectedRoute allowedRoles={["admin"]} />}>
              <Route path="/admin/users" element={<UserManagement />} />
              <Route path="/admin/departments" element={<DepartmentManagement />} />
              <Route path="/admin/assignments" element={<AssignmentManagement />} />
              <Route path="/admin/audit-log" element={<AuditLog />} />
              <Route path="/admin/settings" element={<div>Settings (coming in Phase 2)</div>} />
            </Route>
          </Route>
        </Route>
        <Route path="*" element={<NotFound />} />
      </Routes>
      <Toaster />
    </ErrorBoundary>
  );
}

export default App;
