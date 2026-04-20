import { lazy, Suspense, useEffect } from "react";
import { Route, Routes } from "react-router-dom";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import AppLayout from "@/components/layout/AppLayout";
import ProtectedRoute from "@/components/layout/ProtectedRoute";
import { Toaster } from "@/components/ui/sonner";
import { useAuthStore } from "@/stores/authStore";

// Lazy load all route components
const Login = lazy(() => import("@/pages/Login"));
const Register = lazy(() => import("@/pages/Register"));
const VerifyEmail = lazy(() => import("@/pages/VerifyEmail"));
const DashboardRouter = lazy(() => import("@/pages/DashboardRouter"));
const CaseInputForm = lazy(() => import("@/pages/CaseInputForm"));
const RotationTracker = lazy(() => import("@/pages/RotationTracker"));
const SubmissionHistory = lazy(() => import("@/pages/SubmissionHistory"));
const NotificationHistory = lazy(() => import("@/pages/NotificationHistory"));
const UserManagement = lazy(() => import("@/pages/admin/UserManagement"));
const DepartmentManagement = lazy(
	() => import("@/pages/admin/DepartmentManagement"),
);
const AssignmentManagement = lazy(
	() => import("@/pages/admin/AssignmentManagement"),
);
const AuditLog = lazy(() => import("@/pages/admin/AuditLog"));
const DeletedSubmissions = lazy(
	() => import("@/pages/admin/DeletedSubmissions"),
);
const Settings = lazy(() => import("@/pages/Settings"));
const PendingChanges = lazy(() => import("@/pages/admin/PendingChanges"));
const InviteCodes = lazy(() => import("@/pages/admin/InviteCodes"));
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
					<Route path="/register" element={<Register />} />
					<Route path="/verify-email" element={<VerifyEmail />} />
					<Route element={<ProtectedRoute />}>
						<Route element={<AppLayout />}>
							<Route path="/" element={<DashboardRouter />} />
							<Route path="/cases/new" element={<CaseInputForm />} />
							<Route path="/rotation-tracker" element={<RotationTracker />} />
							<Route path="/submissions" element={<SubmissionHistory />} />
							<Route path="/notifications" element={<NotificationHistory />} />
							<Route path="/settings" element={<Settings />} />
							<Route element={<ProtectedRoute allowedRoles={["admin"]} />}>
								<Route path="/admin/users" element={<UserManagement />} />
								<Route
									path="/admin/departments"
									element={<DepartmentManagement />}
								/>
								<Route
									path="/admin/assignments"
									element={<AssignmentManagement />}
								/>
								<Route path="/admin/audit-log" element={<AuditLog />} />
								<Route
									path="/admin/deleted-submissions"
									element={<DeletedSubmissions />}
								/>
								<Route
									path="/admin/invite-codes"
									element={<InviteCodes />}
								/>
								<Route
									path="/admin/pending-changes"
									element={<PendingChanges />}
								/>
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
