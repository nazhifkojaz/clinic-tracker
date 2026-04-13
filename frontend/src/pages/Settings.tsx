import { Loader2, Save } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuthStore } from "@/stores/authStore";
import { departmentService } from "@/services/departments";
import { userService } from "@/services/users";
import type { Department } from "@/types/department";
import type { PendingChange, ProfileUpdateRequest } from "@/types/user";

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
};

export default function Settings() {
	const { user, initialize } = useAuthStore();
	const [departments, setDepartments] = useState<Department[]>([]);

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
	});
	const [profileError, setProfileError] = useState("");
	const [isSavingProfile, setIsSavingProfile] = useState(false);

	// Pending changes
	const [pendingChanges, setPendingChanges] = useState<PendingChange[]>([]);

	useEffect(() => {
		if (user) {
			setProfileForm({
				full_name: user.full_name,
				institutional_id: user.institutional_id ?? "",
				department_id: user.department_id ?? null,
			});
		}
	}, [user]);

	useEffect(() => {
		if (user?.role === "supervisor") {
			departmentService.list().then((depts) =>
				setDepartments(depts.filter((d) => d.is_active)),
			);
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
			profileForm.institutional_id !== user?.institutional_id
		) {
			updateData.institutional_id = profileForm.institutional_id || null;
		}
		if (
			user?.role === "supervisor" &&
			profileForm.department_id !== user?.department_id
		) {
			updateData.department_id = profileForm.department_id;
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
							<Label htmlFor="profile_full_name">Full Name</Label>
							<Input
								id="profile_full_name"
								value={profileForm.full_name ?? ""}
								onChange={(e) =>
									setProfileForm({
										...profileForm,
										full_name: e.target.value,
									})
								}
								required
							/>
						</div>
						<div className="space-y-2">
							<Label htmlFor="profile_institutional_id">
								{user.role === "student" ? "Student ID" : "Staff ID"}
							</Label>
							<Input
								id="profile_institutional_id"
								value={profileForm.institutional_id ?? ""}
								onChange={(e) =>
									setProfileForm({
										...profileForm,
										institutional_id: e.target.value,
									})
								}
							/>
						</div>
						{user.role === "supervisor" && (
							<div className="space-y-2">
								<Label htmlFor="profile_department">Department</Label>
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
												{fieldLabels[change.field_name] || change.field_name}
											</td>
											<td className="p-4 text-muted-foreground">
												{change.old_value || "—"}
											</td>
											<td className="p-4">{change.new_value || "—"}</td>
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
