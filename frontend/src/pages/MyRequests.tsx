import { Loader2, Save } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { fieldLabels, statusBadgeColor } from "@/lib/pendingChanges";
import { assignmentService } from "@/services/assignments";
import { departmentService } from "@/services/departments";
import { studentService } from "@/services/students";
import { userService } from "@/services/users";
import { useAuthStore } from "@/stores/authStore";
import type { AssignmentWithDetails } from "@/types/assignment";
import type { Department } from "@/types/department";
import type { ReviewerInfo } from "@/types/submission";
import type {
	PendingChange,
	ProfileUpdateRequest,
	User,
} from "@/types/user";

export default function MyRequests() {
	const { user } = useAuthStore();
	const [departments, setDepartments] = useState<Department[]>([]);

	// Student-specific data
	const [currentSupervisor, setCurrentSupervisor] =
		useState<ReviewerInfo | null>(null);
	const [supervisors, setSupervisors] = useState<User[]>([]);
	const [selectedSupervisorId, setSelectedSupervisorId] = useState<
		string | null
	>(null);
	const [isRequestingSupervisor, setIsRequestingSupervisor] = useState(false);

	// Supervisor-specific data
	const [assignedStudents, setAssignedStudents] = useState<
		AssignmentWithDetails[]
	>([]);
	const [removalReasons, setRemovalReasons] = useState<Record<string, string>>(
		{},
	);
	const [isRemoving, setIsRemoving] = useState<string | null>(null);

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

	const deptLookup = useMemo(
		() => new Map(departments.map((d) => [d.id, d.name])),
		[departments],
	);
	const supervisorLookup = useMemo(
		() => new Map(supervisors.map((s) => [s.id, s.full_name])),
		[supervisors],
	);
	const studentLookup = useMemo(() => {
		const map = new Map<string, string>();
		for (const a of assignedStudents) {
			if (a.student_id) map.set(a.student_id, a.student_name ?? "Unknown");
		}
		for (const c of pendingChanges) {
			if (
				c.field_name === "remove_student_id" &&
				c.new_value &&
				c.old_value
			) {
				if (!map.has(c.new_value)) map.set(c.new_value, c.old_value);
			}
		}
		return map;
	}, [assignedStudents, pendingChanges]);
	const resolveChangeValue = (
		fieldName: string,
		value: string | null,
	): string => {
		if (!value) return "\u2014";
		switch (fieldName) {
			case "department_id":
				return deptLookup.get(value) ?? value;
			case "supervisor_id":
				return supervisorLookup.get(value) ?? value;
			case "remove_student_id":
				return studentLookup.get(value) ?? value;
			default:
				return value;
		}
	};

	// Only PENDING fields are disabled — rejected/approved ones allow re-request
	const pendingFields = useMemo(
		() =>
			new Set(
				pendingChanges
					.filter((c) => c.status === "pending")
					.map((c) => c.field_name),
			),
		[pendingChanges],
	);

	const pendingRemovalIds = useMemo(
		() =>
			new Set(
				pendingChanges
					.filter(
						(c) =>
							c.field_name === "remove_student_id" &&
							c.status === "pending" &&
							c.new_value,
					)
					.map((c) => c.new_value!),
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
				.catch((err) => {
					console.error("Failed to load academic supervisor", err);
					toast.error("Failed to load supervisor information.");
				});
			userService
				.list({ role: "supervisor", is_active: true, limit: 200 })
				.then((res) => setSupervisors(res.items))
				.catch((err) => {
					console.error("Failed to load supervisors", err);
					toast.error("Failed to load supervisors list.");
				});
		}
		if (user?.role === "supervisor") {
			assignmentService
				.list({ assignment_type: "primary" })
				.then((res) =>
					setAssignedStudents(
						res.items.filter((a) => a.student_id !== null),
					),
				)
				.catch((err) => {
					console.error("Failed to load assigned students", err);
					toast.error("Failed to load assigned students.");
				});
		}
	}, [user?.role]);

	useEffect(() => {
		userService
			.getMyPendingChanges()
			.then(setPendingChanges)
			.catch((err) => {
				console.error("Failed to load pending changes", err);
				toast.error("Failed to load pending changes.");
			});
	}, []);

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
			toast.success("Profile change submitted for admin approval");
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

	const handleRequestRemoval = async (studentId: string) => {
		setIsRemoving(studentId);
		try {
			await userService.updateOwnProfile({
				remove_student_id: studentId,
				reason: removalReasons[studentId] || null,
			});
			toast.success("Student removal submitted for admin approval");
			setRemovalReasons((prev) => {
				const next = { ...prev };
				delete next[studentId];
				return next;
			});
			userService.getMyPendingChanges().then(setPendingChanges);
		} catch (err: unknown) {
			const detail =
				(err as { response?: { data?: { detail?: string } } })?.response?.data
					?.detail || "Failed to request student removal";
			toast.error(detail);
		} finally {
			setIsRemoving(null);
		}
	};

	if (!user) return null;

	return (
		<div className="space-y-6">
			<h1 className="text-2xl font-bold">My Requests</h1>

			{/* Edit Profile */}
			<Card>
				<CardHeader>
					<CardTitle>Edit Profile</CardTitle>
					<p className="text-sm text-muted-foreground">
						Profile changes require admin approval before taking effect.
					</p>
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

			{/* Assigned Students (supervisors only) */}
			{user.role === "supervisor" && assignedStudents.length > 0 && (
				<Card>
					<CardHeader>
						<CardTitle>Assigned Students</CardTitle>
					</CardHeader>
					<CardContent className="space-y-3">
						{assignedStudents.map((assignment) => {
							const studentId = assignment.student_id!;
							const hasPendingRemoval = pendingRemovalIds.has(studentId);
							const isExpanded = removalReasons[studentId] !== undefined || hasPendingRemoval;

							return (
								<div
									key={assignment.id}
									className="rounded-md border p-3 space-y-2"
								>
									<div className="flex items-center justify-between">
										<div>
											<p className="font-medium">
												{assignment.student_name}
											</p>
											<p className="text-sm text-muted-foreground">
												{assignment.department_name ?? "No department"}
											</p>
										</div>
										{hasPendingRemoval ? (
											<span className="rounded-full bg-yellow-100 px-2 py-0.5 text-xs font-medium text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300">
												Removal pending
											</span>
										) : (
											<Button
												variant="outline"
												size="sm"
												onClick={() =>
													setRemovalReasons((prev) => ({
														...prev,
														[studentId]: prev[studentId] ?? "",
													}))
												}
												disabled={isRemoving !== null}
											>
												Request Removal
											</Button>
										)}
									</div>
									{isExpanded && !hasPendingRemoval && (
										<div className="space-y-2 pt-1">
											<textarea
												className="flex min-h-[60px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
												placeholder="Reason (optional)..."
												value={removalReasons[studentId] ?? ""}
												onChange={(e) =>
													setRemovalReasons((prev) => ({
														...prev,
														[studentId]: e.target.value,
													}))
												}
											/>
											<div className="flex justify-end gap-2">
												<Button
													variant="ghost"
													size="sm"
													onClick={() =>
														setRemovalReasons((prev) => {
															const next = { ...prev };
															delete next[studentId];
															return next;
														})
													}
												>
													Cancel
												</Button>
												<Button
													size="sm"
													disabled={isRemoving === studentId}
													onClick={() =>
														handleRequestRemoval(studentId)
													}
												>
													{isRemoving === studentId ? (
														<>
															<Loader2 className="mr-2 h-4 w-4 animate-spin" />
															Submitting...
														</>
													) : (
														"Submit"
													)}
												</Button>
											</div>
										</div>
									)}
								</div>
							);
						})}
					</CardContent>
				</Card>
			)}

			{/* Change Requests History */}
			<Card>
				<CardHeader>
					<CardTitle>Change Requests</CardTitle>
				</CardHeader>
				<CardContent className="p-0">
					{pendingChanges.length === 0 ? (
						<p className="p-6 text-center text-muted-foreground">
							You have no change requests.
						</p>
					) : (
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
												{change.field_name === "remove_student_id"
													? change.old_value || "\u2014"
													: resolveChangeValue(
															change.field_name,
															change.old_value,
														)}
											</td>
											<td className="p-4">
												{change.field_name === "remove_student_id"
													? "Remove"
													: resolveChangeValue(
															change.field_name,
															change.new_value,
														)}
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
					)}
				</CardContent>
			</Card>
		</div>
	);
}
