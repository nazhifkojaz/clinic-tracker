import { Loader2, Save } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuthStore } from "@/stores/authStore";
import { departmentService } from "@/services/departments";
import { studentService } from "@/services/students";
import { userService } from "@/services/users";
import type { Department } from "@/types/department";
import type { ReviewerInfo } from "@/types/submission";
import type { PendingChange, ProfileUpdateRequest, User } from "@/types/user";

const roleBadgeColor: Record<string, string> = {
	admin: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
	supervisor: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
	student: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
};

const statusBadgeColor: Record<string, string> = {
	pending: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300",
	approved: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
	rejected: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
};

const fieldLabels: Record<string, string> = {
	full_name: "Full Name",
	institutional_id: "Institutional ID",
	department_id: "Department",
	email: "Email",
	supervisor_id: "Academic Supervisor",
};

export default function Settings() {
	const { user, initialize } = useAuthStore();
	const [departments, setDepartments] = useState<Department[]>([]);

	// Student-specific data
	const [currentSupervisor, setCurrentSupervisor] =
		useState<ReviewerInfo | null>(null);
	const [supervisors, setSupervisors] = useState<User[]>([]);
	const [selectedSupervisorId, setSelectedSupervisorId] = useState<
		string | null
	>(null);
	const [isRequestingSupervisor, setIsRequestingSupervisor] = useState(false);

	// Password form
	const [pwForm, setPwForm] = useState({
		current_password: "",
		new_password: "",
		confirm_password: "",
	});
	const [pwError, setPwError] = useState("");
	const [isChangingPw, setIsChangingPw] = useState(false);

	// Profile form
	const [profileForm, setProfileForm] = useState<ProfileUpdateRequest>({
		full_name: user?.full_name ?? "",
		institutional_id: user?.institutional_id ?? "",
		department_id: user?.department_id ?? null,
		email: user?.email ?? "",
	});
	const [profileError, setProfileError] = useState("");
	const [isSavingProfile, setIsSavingProfile] = useState(false);

	// Pending changes
	const [pendingChanges, setPendingChanges] = useState<PendingChange[]>([]);

	const pendingFields = useMemo(
		() =>
			new Set(
				pendingChanges
					.filter((c) => c.status === "pending")
					.map((c) => c.field_name),
			),
		[pendingChanges],
	);

	useEffect(() => {
		if (user) {
			setProfileForm({
				full_name: user.full_name,
				institutional_id: user.institutional_id ?? "",
				department_id: user.department_id ?? null,
				email: user.email,
			});
		}
	}, [user]);

	useEffect(() => {
		if (user?.role === "supervisor" || user?.role === "student") {
			departmentService.list().then((depts) =>
				setDepartments(depts.filter((d) => d.is_active)),
			);
		}
	}, [user?.role]);

	useEffect(() => {
		if (user?.role === "student") {
			studentService
				.getAcademicSupervisor()
				.then((res) => setCurrentSupervisor(res.supervisor))
				.catch(() => {});
			userService
				.list({ role: "supervisor", is_active: true, limit: 200 })
				.then((res) => setSupervisors(res.items))
				.catch(() => {});
		}
	}, [user?.role]);

	useEffect(() => {
		userService.getMyPendingChanges().then(setPendingChanges).catch(() => {});
	}, []);

	const handleChangePassword = async (e: React.FormEvent) => {
		e.preventDefault();
		setPwError("");

		if (pwForm.new_password.length < 8) {
			setPwError("New password must be at least 8 characters");
			return;
		}
		if (pwForm.new_password !== pwForm.confirm_password) {
			setPwError("Passwords do not match");
			return;
		}

		setIsChangingPw(true);
		try {
			await userService.changePassword({
				current_password: pwForm.current_password,
				new_password: pwForm.new_password,
			});
			toast.success("Password changed successfully");
			setPwForm({
				current_password: "",
				new_password: "",
				confirm_password: "",
			});
		} catch (err: unknown) {
			const detail =
				(err as { response?: { data?: { detail?: string } } })?.response?.data
					?.detail || "Failed to change password";
			setPwError(detail);
		} finally {
			setIsChangingPw(false);
		}
	};

	const handleProfileSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		setProfileError("");

		const updateData: ProfileUpdateRequest = {};
		if (profileForm.full_name && profileForm.full_name !== user?.full_name) {
			updateData.full_name = profileForm.full_name;
		}
		if (
			profileForm.institutional_id !== undefined &&
			(profileForm.institutional_id || null) !== (user?.institutional_id ?? null)
		) {
			updateData.institutional_id = profileForm.institutional_id || null;
		}
		if (
			(user?.role === "supervisor" || user?.role === "student") &&
			profileForm.department_id !== user?.department_id
		) {
			updateData.department_id = profileForm.department_id;
		}
		if (
			user?.role !== "admin" &&
			profileForm.email &&
			profileForm.email !== user?.email
		) {
			updateData.email = profileForm.email;
		}

		if (!Object.keys(updateData).length) {
			setProfileError("No changes to save");
			return;
		}

		setIsSavingProfile(true);
		try {
			await userService.updateOwnProfile(updateData);
			if (user?.role === "admin") {
				toast.success("Profile updated");
				await initialize();
			} else {
				toast.success("Profile change submitted for admin approval");
			}
			userService.getMyPendingChanges().then(setPendingChanges);
		} catch (err: unknown) {
			const detail =
				(err as { response?: { data?: { detail?: string } } })?.response?.data
					?.detail || "Failed to update profile";
			setProfileError(detail);
		} finally {
			setIsSavingProfile(false);
		}
	};

	const handleRequestSupervisorChange = async () => {
		if (!selectedSupervisorId) return;
		setIsRequestingSupervisor(true);
		try {
			await userService.updateOwnProfile({ supervisor_id: selectedSupervisorId });
			toast.success("Supervisor change submitted for admin approval");
			setSelectedSupervisorId(null);
			userService.getMyPendingChanges().then(setPendingChanges);
		} catch (err: unknown) {
			const detail =
				(err as { response?: { data?: { detail?: string } } })?.response?.data
					?.detail || "Failed to request supervisor change";
			toast.error(detail);
		} finally {
			setIsRequestingSupervisor(false);
		}
	};

	if (!user) return null;

	return (
		<div className="space-y-6">
			<h1 className="text-2xl font-bold">Settings</h1>

			{/* Account Information */}
			<Card>
				<CardHeader>
					<CardTitle>Account Information</CardTitle>
				</CardHeader>
				<CardContent>
					<div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
						<div>
							<span className="text-sm text-muted-foreground">Email</span>
							<p className="font-medium">{user.email}</p>
						</div>
						<div>
							<span className="text-sm text-muted-foreground">Role</span>
							<p>
								<span
									className={`inline-block rounded-full px-2 py-1 text-xs font-medium capitalize ${roleBadgeColor[user.role]}`}
								>
									{user.role}
								</span>
							</p>
						</div>
						<div>
							<span className="text-sm text-muted-foreground">
								{user.role === "student" ? "Student ID" : "Staff ID"}
							</span>
							<p className="font-medium">{user.institutional_id || "—"}</p>
						</div>
						<div>
							<span className="text-sm text-muted-foreground">Registered</span>
							<p className="font-medium">
								{new Date(user.created_at).toLocaleDateString()}
							</p>
						</div>
					</div>
				</CardContent>
			</Card>

			{/* Change Password */}
			<Card>
				<CardHeader>
					<CardTitle>Change Password</CardTitle>
				</CardHeader>
				<CardContent>
					<form onSubmit={handleChangePassword} className="space-y-4">
						{pwError && (
							<div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
								{pwError}
							</div>
						)}
						<div className="space-y-2">
							<Label htmlFor="current_password">Current Password</Label>
							<Input
								id="current_password"
								type="password"
								value={pwForm.current_password}
								onChange={(e) =>
									setPwForm({ ...pwForm, current_password: e.target.value })
								}
								required
							/>
						</div>
						<div className="space-y-2">
							<Label htmlFor="new_password">New Password</Label>
							<Input
								id="new_password"
								type="password"
								value={pwForm.new_password}
								onChange={(e) =>
									setPwForm({ ...pwForm, new_password: e.target.value })
								}
								required
								minLength={8}
							/>
						</div>
						<div className="space-y-2">
							<Label htmlFor="confirm_password">Confirm New Password</Label>
							<Input
								id="confirm_password"
								type="password"
								value={pwForm.confirm_password}
								onChange={(e) =>
									setPwForm({ ...pwForm, confirm_password: e.target.value })
								}
								required
								minLength={8}
							/>
						</div>
						<div className="flex justify-end">
							<Button type="submit" disabled={isChangingPw}>
								{isChangingPw ? (
									<>
										<Loader2 className="mr-2 h-4 w-4 animate-spin" />
										Changing...
									</>
								) : (
									"Change Password"
								)}
							</Button>
						</div>
					</form>
				</CardContent>
			</Card>

			{/* Edit Profile */}
			<Card>
				<CardHeader>
					<CardTitle>Edit Profile</CardTitle>
					{user.role !== "admin" && (
						<p className="text-sm text-muted-foreground">
							Profile changes require admin approval before taking effect.
						</p>
					)}
				</CardHeader>
				<CardContent>
					<form onSubmit={handleProfileSubmit} className="space-y-4">
						{profileError && (
							<div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
								{profileError}
							</div>
						)}
						<div className="space-y-2">
							<div className="flex items-center gap-2">
								<Label htmlFor="profile_full_name">Full Name</Label>
								{pendingFields.has("full_name") && (
									<span className="rounded-full bg-yellow-100 px-2 py-0.5 text-xs font-medium text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300">
										Pending
									</span>
								)}
							</div>
							<Input
								id="profile_full_name"
								value={profileForm.full_name ?? ""}
								onChange={(e) =>
									setProfileForm({
										...profileForm,
										full_name: e.target.value,
									})
								}
								disabled={pendingFields.has("full_name")}
								required
							/>
						</div>
						<div className="space-y-2">
							<div className="flex items-center gap-2">
								<Label htmlFor="profile_institutional_id">
									{user.role === "student" ? "Student ID" : "Staff ID"}
								</Label>
								{pendingFields.has("institutional_id") && (
									<span className="rounded-full bg-yellow-100 px-2 py-0.5 text-xs font-medium text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300">
										Pending
									</span>
								)}
							</div>
							<Input
								id="profile_institutional_id"
								value={profileForm.institutional_id ?? ""}
								onChange={(e) =>
									setProfileForm({
										...profileForm,
										institutional_id: e.target.value,
									})
								}
								disabled={pendingFields.has("institutional_id")}
							/>
						</div>
						{user.role !== "admin" && (
							<div className="space-y-2">
								<div className="flex items-center gap-2">
									<Label htmlFor="profile_email">Email</Label>
									{pendingFields.has("email") && (
										<span className="rounded-full bg-yellow-100 px-2 py-0.5 text-xs font-medium text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300">
											Pending
										</span>
									)}
								</div>
								<Input
									id="profile_email"
									type="email"
									value={profileForm.email ?? ""}
									onChange={(e) =>
										setProfileForm({
											...profileForm,
											email: e.target.value,
										})
									}
									disabled={pendingFields.has("email")}
								/>
								<p className="text-xs text-muted-foreground">
									Changing your email requires admin approval, then verification
									of the new address.
								</p>
							</div>
						)}
						{(user.role === "supervisor" || user.role === "student") && (
							<div className="space-y-2">
								<div className="flex items-center gap-2">
									<Label htmlFor="profile_department">Department</Label>
									{pendingFields.has("department_id") && (
										<span className="rounded-full bg-yellow-100 px-2 py-0.5 text-xs font-medium text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300">
											Pending
										</span>
									)}
								</div>
								<select
									id="profile_department"
									className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm"
									value={profileForm.department_id ?? ""}
									onChange={(e) =>
										setProfileForm({
											...profileForm,
											department_id: e.target.value || null,
										})
									}
									disabled={pendingFields.has("department_id")}
								>
									<option value="">No department</option>
									{departments.map((dept) => (
										<option key={dept.id} value={dept.id}>
											{dept.name}
										</option>
									))}
								</select>
							</div>
						)}
						<div className="flex justify-end">
							<Button type="submit" disabled={isSavingProfile}>
								{isSavingProfile ? (
									<>
										<Loader2 className="mr-2 h-4 w-4 animate-spin" />
										Saving...
									</>
								) : (
									<>
										<Save className="mr-2 h-4 w-4" />
										Save Changes
									</>
								)}
							</Button>
						</div>
					</form>
				</CardContent>
			</Card>

			{/* Academic Supervisor (students only) */}
			{user.role === "student" && (
				<Card>
					<CardHeader>
						<CardTitle>Academic Supervisor</CardTitle>
					</CardHeader>
					<CardContent className="space-y-4">
						<div>
							<span className="text-sm text-muted-foreground">
								Current Supervisor
							</span>
							<p className="font-medium">
								{currentSupervisor?.full_name ?? "No supervisor assigned"}
							</p>
						</div>
						<div className="space-y-2">
							<div className="flex items-center gap-2">
								<Label htmlFor="supervisor_select">
									Request Supervisor Change
								</Label>
								{pendingFields.has("supervisor_id") && (
									<span className="rounded-full bg-yellow-100 px-2 py-0.5 text-xs font-medium text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300">
										Pending
									</span>
								)}
							</div>
							<select
								id="supervisor_select"
								className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm"
								value={selectedSupervisorId ?? ""}
								onChange={(e) =>
									setSelectedSupervisorId(e.target.value || null)
								}
								disabled={pendingFields.has("supervisor_id")}
							>
								<option value="">Select a supervisor...</option>
								{supervisors.map((sup) => (
									<option key={sup.id} value={sup.id}>
										{sup.full_name}
									</option>
								))}
							</select>
						</div>
						<div className="flex justify-end">
							<Button
								onClick={handleRequestSupervisorChange}
								disabled={
									!selectedSupervisorId ||
									isRequestingSupervisor ||
									pendingFields.has("supervisor_id")
								}
							>
								{isRequestingSupervisor ? (
									<>
										<Loader2 className="mr-2 h-4 w-4 animate-spin" />
										Submitting...
									</>
								) : (
									"Request Change"
								)}
							</Button>
						</div>
					</CardContent>
				</Card>
			)}

			{/* Pending Changes */}
			{pendingChanges.length > 0 && (
				<Card>
					<CardHeader>
						<CardTitle>Pending Changes</CardTitle>
					</CardHeader>
					<CardContent className="p-0">
						<div className="overflow-x-auto">
							<table className="w-full min-w-[500px]">
								<thead>
									<tr className="border-b text-left text-sm text-muted-foreground">
										<th className="p-4">Field</th>
										<th className="p-4">Current</th>
										<th className="p-4">Requested</th>
										<th className="p-4">Status</th>
										<th className="p-4">Date</th>
									</tr>
								</thead>
								<tbody>
									{pendingChanges.map((change) => (
										<tr key={change.id} className="border-b last:border-0">
											<td className="p-4 font-medium">
												{fieldLabels[change.field_name] ||
													change.field_name}
											</td>
											<td className="p-4 text-muted-foreground">
												{change.old_value || "—"}
											</td>
											<td className="p-4">
												{change.new_value || "—"}
											</td>
											<td className="p-4">
												<span
													className={`rounded-full px-2 py-1 text-xs font-medium capitalize ${statusBadgeColor[change.status]}`}
												>
													{change.status}
												</span>
											</td>
											<td className="p-4 text-sm text-muted-foreground">
												{new Date(change.created_at).toLocaleDateString()}
											</td>
										</tr>
									))}
								</tbody>
							</table>
						</div>
					</CardContent>
				</Card>
			)}
		</div>
	);
}
