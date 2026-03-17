import { useEffect, lazy, Suspense } from "react";
import { Routes, Route } from "react-router-dom";
import { useAuthStore } from "@/stores/authStore";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { Toaster } from "@/components/ui/sonner";
import ProtectedRoute from "@/components/layout/ProtectedRoute";
import AppLayout from "@/components/layout/AppLayout";

// Lazy load all route components
const Login = lazy(() => import("@/pages/Login"));
const DashboardRouter = lazy(() => import("@/pages/DashboardRouter"));
const CaseInputForm = lazy(() => import("@/pages/CaseInputForm"));
const SubmissionHistory = lazy(() => import("@/pages/SubmissionHistory"));
const SendNotification = lazy(() => import("@/pages/SendNotification"));
const NotificationHistory = lazy(() => import("@/pages/NotificationHistory"));
const UserManagement = lazy(() => import("@/pages/admin/UserManagement"));
const DepartmentManagement = lazy(() => import("@/pages/admin/DepartmentManagement"));
const AssignmentManagement = lazy(() => import("@/pages/admin/AssignmentManagement"));
const AuditLog = lazy(() => import("@/pages/admin/AuditLog"));
const NotFound = lazy(() => import("@/pages/NotFound"));

// Simple loading spinner
function LoadingSpinner() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
    </div>
  );
}

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
      <Suspense fallback={<LoadingSpinner />}>
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
      </Suspense>
      <Toaster />
    </ErrorBoundary>
  );
}

export default App;
