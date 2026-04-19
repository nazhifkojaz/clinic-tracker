import {
	ChevronLeft,
	ChevronRight,
	Loader2,
	Pencil,
	Plus,
	RotateCw,
	Trash2,
} from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuthStore } from "@/stores/authStore";
import { departmentService } from "@/services/departments";
import { rotationService } from "@/services/rotations";
import { userService } from "@/services/users";
import type { Department } from "@/types/department";
import type { Rotation } from "@/types/rotation";
import type { User, UserCreate, UserRole } from "@/types/user";

const PAGE_SIZE = 25;
const MS_PER_DAY = 86_400_000;

type AssignmentMode = "change_dept" | "adjust_day";

export default function UserManagement() {
	const [users, setUsers] = useState<User[]>([]);
	const [totalCount, setTotalCount] = useState(0);
	const [currentPage, setCurrentPage] = useState(0);
	const [hasMore, setHasMore] = useState(false);
	const [isLoading, setIsLoading] = useState(false);

	const [pendingUsers, setPendingUsers] = useState<User[]>([]);
	const [isApprovingId, setIsApprovingId] = useState<string | null>(null);

	const [isModalOpen, setIsModalOpen] = useState(false);
	const [editingUser, setEditingUser] = useState<User | null>(null);
	const [formData, setFormData] = useState({
		email: "",
		password: "",
		full_name: "",
		institutional_id: "",
		role: "student" as UserRole,
	});
	const [error, setError] = useState("");
	const [isSubmitting, setIsSubmitting] = useState(false);

	// Assignment modal state
	const [isAssignModalOpen, setIsAssignModalOpen] = useState(false);
	const [assignTarget, setAssignTarget] = useState<User | null>(null);
	const [assignMode, setAssignMode] = useState<AssignmentMode>("change_dept");
	const [currentRotation, setCurrentRotation] = useState<Rotation | null>(
		null,
	);
	const [isLoadingRotation, setIsLoadingRotation] = useState(false);
	const [selectedDeptId, setSelectedDeptId] = useState("");
	const [startDayOffset, setStartDayOffset] = useState(0);
	const [adjustTotalDay, setAdjustTotalDay] = useState(0);
	const [isAssignSubmitting, setIsAssignSubmitting] = useState(false);
	const [assignError, setAssignError] = useState("");
	const [departments, setDepartments] = useState<Department[]>([]);

	const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
	const [deleteTargetUser, setDeleteTargetUser] = useState<User | null>(null);
	const [isDeleting, setIsDeleting] = useState(false);

	const currentUser = useAuthStore((s) => s.user);

	const fetchUsers = async (page: number = currentPage) => {
		try {
			setIsLoading(true);
			const response = await userService.list({
				limit: PAGE_SIZE,
				offset: page * PAGE_SIZE,
			});
			setUsers(response.items);
			setTotalCount(response.total);
			setHasMore(response.has_more);
			setError("");
		} catch {
			setError("Failed to load users. Please refresh the page.");
		} finally {
			setIsLoading(false);
		}
	};

	const fetchPendingUsers = async () => {
		try {
			const response = await userService.list({
				pending_approval: true,
				limit: 200,
			});
			setPendingUsers(response.items);
		} catch {
			// Non-critical, don't show error
		}
	};

	useEffect(() => {
		Promise.all([
			fetchUsers(),
			fetchPendingUsers(),
			departmentService.list().then((depts) => {
				setDepartments(depts.filter((d) => d.is_active));
			}),
		]);
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, []);

	const handlePageChange = (newPage: number) => {
		setCurrentPage(newPage);
		fetchUsers(newPage);
	};

	const handleApprove = async (userId: string) => {
		setIsApprovingId(userId);
		try {
			await userService.update(userId, { is_active: true });
			toast.success("User approved successfully");
			await Promise.all([fetchPendingUsers(), fetchUsers(currentPage)]);
		} catch {
			toast.error("Failed to approve user");
		} finally {
			setIsApprovingId(null);
		}
	};

	const openCreateModal = () => {
		setEditingUser(null);
		setFormData({
			email: "",
			password: "",
			full_name: "",
			institutional_id: "",
			role: "student",
		});
		setError("");
		setIsModalOpen(true);
	};

	const openEditModal = (user: User) => {
		setEditingUser(user);
		setFormData({
			email: user.email,
			password: "",
			full_name: user.full_name,
			institutional_id: user.institutional_id || "",
			role: user.role,
		});
		setError("");
		setIsModalOpen(true);
	};

	const handleSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		setIsSubmitting(true);
		setError("");

		try {
			if (editingUser) {
				const updateData: Record<string, unknown> = {
					email: formData.email,
					full_name: formData.full_name,
					institutional_id: formData.institutional_id || null,
					role: formData.role,
				};
				if (formData.password) updateData.password = formData.password;
				await userService.update(editingUser.id, updateData);
			} else {
				await userService.create(formData as UserCreate);
			}
			setIsModalOpen(false);
			fetchUsers(currentPage);
		} catch {
			setError(
				editingUser
					? "Failed to update user."
					: "Failed to create user. Email or ID may already exist.",
			);
		} finally {
			setIsSubmitting(false);
		}
	};

	// --- Assignment modal helpers ---

	const getDeptName = (deptId: string | null) => {
		if (!deptId) return null;
		return departments.find((d) => d.id === deptId)?.name ?? null;
	};

	const calcRotationDay = (
		rotation: Rotation,
		dept: Department | undefined,
	) => {
		if (!dept) return { current: 0, total: 0 };
		const elapsed = Math.max(
			0,
			Math.floor(
				(Date.now() - new Date(rotation.started_at).getTime()) / MS_PER_DAY,
			),
		);
		const current = rotation.days_offset + elapsed;
		return { current, total: dept.rotation_duration_days };
	};

	const openAssignModal = async (user: User) => {
		setAssignTarget(user);
		setAssignError("");
		setSelectedDeptId("");
		setStartDayOffset(0);
		setAdjustTotalDay(0);
		setCurrentRotation(null);
		setAssignMode("change_dept");

		if (user.role === "student") {
			setIsLoadingRotation(true);
			try {
				const rotation = await rotationService.getStudentCurrent(user.id);
				setCurrentRotation(rotation);
				if (rotation) {
					const dept = departments.find((d) => d.id === rotation.department_id);
					const { current, total } = calcRotationDay(rotation, dept);
					setAdjustTotalDay(current);
				}
			} catch {
				// Rotation fetch failed — treat as no rotation
			} finally {
				setIsLoadingRotation(false);
			}
		}

		setIsAssignModalOpen(true);
	};

	const handleAssignSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		if (!assignTarget) return;

		setIsAssignSubmitting(true);
		setAssignError("");

		try {
			if (assignTarget.role === "supervisor") {
				await userService.update(assignTarget.id, {
					department_id: selectedDeptId || null,
				});
			} else if (assignMode === "change_dept" || !currentRotation) {
				await rotationService.overrideDepartment(assignTarget.id, {
					department_id: selectedDeptId,
					days_offset: startDayOffset,
				});
			} else {
				await rotationService.adjustDay(assignTarget.id, adjustTotalDay);
			}
			toast.success("Assignment updated successfully");
			setIsAssignModalOpen(false);
			fetchUsers(currentPage);
		} catch {
			setAssignError("Failed to update assignment.");
		} finally {
			setIsAssignSubmitting(false);
		}
	};

	const openDeleteModal = (user: User) => {
		setDeleteTargetUser(user);
		setIsDeleteModalOpen(true);
	};

	const handleDelete = async (mode: "soft" | "hard") => {
		if (!deleteTargetUser) return;
		setIsDeleting(true);
		try {
			await userService.delete(deleteTargetUser.id, mode);
			toast.success(
				mode === "soft"
					? "User deactivated successfully"
					: "User permanently deleted",
			);
			setIsDeleteModalOpen(false);
			setDeleteTargetUser(null);
			await Promise.all([fetchUsers(currentPage), fetchPendingUsers()]);
		} catch {
			toast.error("Failed to delete user");
		} finally {
			setIsDeleting(false);
		}
	};

	const idLabel = (role: UserRole) =>
		role === "student" ? "Student ID" : "Staff ID";

	const roleBadgeColor: Record<UserRole, string> = {
		admin: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
		supervisor: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
		student:
			"bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
	};

	// Derived values for assignment modal
	const assignDeptName = assignTarget
		? currentRotation
			? getDeptName(currentRotation.department_id)
			: getDeptName(assignTarget.department_id)
		: null;

	const assignRotationInfo = (() => {
		if (!currentRotation || !assignTarget) return null;
		const dept = departments.find(
			(d) => d.id === currentRotation.department_id,
		);
		return calcRotationDay(currentRotation, dept);
	})();

	const isStudent = assignTarget?.role === "student";
	const hasRotation = currentRotation !== null;

	return (
		<div className="space-y-6">
			<div className="flex items-center justify-between">
				<h1 className="text-2xl font-bold">User Management</h1>
				<Button onClick={openCreateModal}>
					<Plus className="mr-2 h-4 w-4" />
					Create User
				</Button>
			</div>

			{/* Pending Approval Section */}
			{pendingUsers.length > 0 && (
				<Card>
					<CardHeader>
						<CardTitle>
							Pending Approval ({pendingUsers.length})
						</CardTitle>
					</CardHeader>
					<CardContent className="p-0">
						<div className="overflow-x-auto">
							<table className="w-full min-w-[600px]">
								<thead>
									<tr className="border-b text-left text-sm text-muted-foreground">
										<th className="p-4">Name</th>
										<th className="p-4">Email</th>
										<th className="p-4">Role</th>
										<th className="p-4">ID</th>
										<th className="p-4">Registered</th>
										<th className="p-4">Actions</th>
									</tr>
								</thead>
								<tbody>
									{pendingUsers.map((user) => (
										<tr key={user.id} className="border-b last:border-0">
											<td className="p-4 font-medium">{user.full_name}</td>
											<td className="p-4 text-muted-foreground">
												{user.email}
											</td>
											<td className="p-4">
												<span
													className={`rounded-full px-2 py-1 text-xs font-medium capitalize ${roleBadgeColor[user.role]}`}
												>
													{user.role}
												</span>
											</td>
											<td className="p-4 text-muted-foreground">
												{user.institutional_id || "—"}
											</td>
											<td className="p-4 text-muted-foreground">
												{new Date(user.created_at).toLocaleDateString()}
											</td>
											<td className="p-4">
												<Button
													size="sm"
													onClick={() => handleApprove(user.id)}
													disabled={isApprovingId === user.id}
												>
													{isApprovingId === user.id ? (
														<>
															<Loader2 className="mr-1 h-3 w-3 animate-spin" />
															Approving...
														</>
													) : (
														"Approve"
													)}
												</Button>
											</td>
										</tr>
									))}
								</tbody>
							</table>
						</div>
					</CardContent>
				</Card>
			)}

			<Card>
				<CardContent className="p-0">
					<div className="overflow-x-auto">
						<table className="w-full min-w-[600px]">
							<thead>
								<tr className="border-b text-left text-sm text-muted-foreground">
									<th className="p-4">Name</th>
									<th className="p-4">Email</th>
									<th className="p-4">Role</th>
									<th className="p-4">Status</th>
									<th className="p-4">Actions</th>
								</tr>
							</thead>
							<tbody>
								{users.map((user) => (
									<tr key={user.id} className="border-b last:border-0">
										<td className="p-4 font-medium">{user.full_name}</td>
										<td className="p-4 text-muted-foreground">{user.email}</td>
										<td className="p-4">
											<span
												className={`rounded-full px-2 py-1 text-xs font-medium capitalize ${roleBadgeColor[user.role]}`}
											>
												{user.role}
											</span>
										</td>
										<td className="p-4">
											<span
												className={`text-sm ${user.is_active ? "text-green-600" : "text-red-500"}`}
											>
												{user.is_active ? "Active" : "Inactive"}
											</span>
										</td>
										<td className="p-4">
											<div className="flex items-center gap-1">
												{(user.role === "student" ||
													user.role === "supervisor") && (
													<Button
														variant="ghost"
														size="sm"
														onClick={() => openAssignModal(user)}
														title="Manage Assignment"
													>
														<RotateCw className="h-4 w-4" />
													</Button>
												)}
												<Button
													variant="ghost"
													size="icon-sm"
													onClick={() => openEditModal(user)}
												>
													<Pencil className="h-4 w-4" />
												</Button>
												<Button
													variant="ghost"
													size="icon-sm"
													onClick={() => openDeleteModal(user)}
													disabled={user.id === currentUser?.id}
													title={
														user.id === currentUser?.id
															? "Cannot delete yourself"
															: "Delete User"
													}
												>
													<Trash2 className="h-4 w-4 text-destructive" />
												</Button>
											</div>
										</td>
									</tr>
								))}
							</tbody>
						</table>
					</div>

					{totalCount > 0 && (
						<div className="flex items-center justify-between border-t px-4 py-3">
							<div className="text-sm text-muted-foreground">
								Showing {currentPage * PAGE_SIZE + 1} -{" "}
								{Math.min((currentPage + 1) * PAGE_SIZE, totalCount)} of{" "}
								{totalCount}
							</div>
							<div className="flex items-center gap-2">
								<button
									onClick={() =>
										handlePageChange(Math.max(0, currentPage - 1))
									}
									disabled={currentPage === 0 || isLoading}
									className="inline-flex items-center gap-1 rounded-md border px-3 py-2 text-sm font-medium hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
								>
									<ChevronLeft className="h-4 w-4" />
									Previous
								</button>
								<span className="text-sm">
									Page {currentPage + 1} of{" "}
									{Math.ceil(totalCount / PAGE_SIZE)}
								</span>
								<button
									onClick={() => handlePageChange(currentPage + 1)}
									disabled={!hasMore || isLoading}
									className="inline-flex items-center gap-1 rounded-md border px-3 py-2 text-sm font-medium hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
								>
									Next
									<ChevronRight className="h-4 w-4" />
								</button>
							</div>
						</div>
					)}
				</CardContent>
			</Card>

			{/* Edit/Create User Modal */}
			{isModalOpen && (
				<div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
					<Card className="w-full max-w-md">
						<CardHeader>
							<CardTitle>
								{editingUser ? "Edit User" : "Create User"}
							</CardTitle>
						</CardHeader>
						<CardContent>
							<form onSubmit={handleSubmit} className="space-y-4">
								{error && (
									<div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
										{error}
									</div>
								)}
								<div className="space-y-2">
									<Label htmlFor="full_name">Full Name</Label>
									<Input
										id="full_name"
										value={formData.full_name}
										onChange={(e) =>
											setFormData({ ...formData, full_name: e.target.value })
										}
										required
									/>
								</div>
								<div className="space-y-2">
									<Label htmlFor="modal_email">Email</Label>
									<Input
										id="modal_email"
										type="email"
										value={formData.email}
										onChange={(e) =>
											setFormData({ ...formData, email: e.target.value })
										}
										required
									/>
								</div>
								<div className="space-y-2">
									<Label htmlFor="modal_password">
										Password{" "}
										{editingUser && "(leave blank to keep current)"}
									</Label>
									<Input
										id="modal_password"
										type="password"
										value={formData.password}
										onChange={(e) =>
											setFormData({ ...formData, password: e.target.value })
										}
										required={!editingUser}
									/>
								</div>
								<div className="space-y-2">
									<Label htmlFor="role">Role</Label>
									<select
										id="role"
										className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm"
										value={formData.role}
										onChange={(e) =>
											setFormData({
												...formData,
												role: e.target.value as UserRole,
											})
										}
									>
										<option value="student">Student</option>
										<option value="supervisor">Supervisor</option>
										<option value="admin">Admin</option>
									</select>
								</div>
								<div className="space-y-2">
									<Label htmlFor="institutional_id">
										{idLabel(formData.role)}
									</Label>
									<Input
										id="institutional_id"
										value={formData.institutional_id}
										onChange={(e) =>
											setFormData({
												...formData,
												institutional_id: e.target.value,
											})
										}
									/>
								</div>
								<div className="flex justify-end gap-2">
									<Button
										type="button"
										variant="outline"
										onClick={() => setIsModalOpen(false)}
									>
										Cancel
									</Button>
									<Button type="submit" disabled={isSubmitting}>
										{isSubmitting ? (
											<>
												<Loader2 className="mr-2 h-4 w-4 animate-spin" />
												Saving...
											</>
										) : editingUser ? (
											"Update"
										) : (
											"Create"
										)}
									</Button>
								</div>
							</form>
						</CardContent>
					</Card>
				</div>
			)}

			{/* Manage Assignment Modal */}
			{isAssignModalOpen && assignTarget && (
				<div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
					<Card className="w-full max-w-md">
						<CardHeader>
							<CardTitle>
								Manage Assignment — {assignTarget.full_name}
							</CardTitle>
						</CardHeader>
						<CardContent>
							{isLoadingRotation ? (
								<div className="flex items-center justify-center py-8">
									<Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
								</div>
							) : (
								<form
									onSubmit={handleAssignSubmit}
									className="space-y-4"
								>
									{assignError && (
										<div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
											{assignError}
										</div>
									)}

									{/* Current state display */}
									{isStudent && hasRotation && assignRotationInfo ? (
										<div className="rounded-md bg-muted p-3 text-sm">
											<div className="font-medium">
												Current: {assignDeptName ?? "Unknown"}
											</div>
											<div className="text-muted-foreground">
												Day {assignRotationInfo.current} of{" "}
												{assignRotationInfo.total}
											</div>
										</div>
									) : isStudent && !hasRotation ? (
										<div className="rounded-md bg-muted p-3 text-sm text-muted-foreground">
											No active rotation
										</div>
									) : (
										<div className="rounded-md bg-muted p-3 text-sm">
											<div className="font-medium">
												Current:{" "}
												{assignDeptName ?? (
													<span className="text-muted-foreground">
														No department assigned
													</span>
												)}
											</div>
										</div>
									)}

									{/* Mode tabs for students with rotation */}
									{isStudent && hasRotation && (
										<div className="flex gap-2">
											<Button
												type="button"
												variant={
													assignMode === "change_dept"
														? "default"
														: "outline"
												}
												size="sm"
												onClick={() =>
													setAssignMode("change_dept")
												}
											>
												Change Department
											</Button>
											<Button
												type="button"
												variant={
													assignMode === "adjust_day"
														? "default"
														: "outline"
												}
												size="sm"
												onClick={() =>
													setAssignMode("adjust_day")
												}
											>
												Adjust Day
											</Button>
										</div>
									)}

									{/* Change Department fields */}
									{(assignMode === "change_dept" ||
										!isStudent ||
										!hasRotation) && (
										<>
											<div className="space-y-2">
												<Label htmlFor="assign-dept-select">
													{isStudent && !hasRotation
														? "Department"
														: "New Department"}
												</Label>
												<select
													id="assign-dept-select"
													className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm"
													value={selectedDeptId}
													onChange={(e) =>
														setSelectedDeptId(e.target.value)
													}
													required
												>
													<option value="" disabled>
														Select a department
													</option>
													{departments.map((dept) => (
														<option
															key={dept.id}
															value={dept.id}
														>
															{dept.name}
														</option>
													))}
												</select>
											</div>

											{isStudent && (
												<div className="space-y-2">
													<Label htmlFor="start-day-offset">
														Start at day
													</Label>
													<Input
														id="start-day-offset"
														type="number"
														min={0}
														value={startDayOffset}
														onChange={(e) =>
															setStartDayOffset(
																Number(e.target.value),
															)
														}
													/>
													<p className="text-xs text-muted-foreground">
														Number of days to credit toward
														progress in the new department.
													</p>
												</div>
											)}

											{isStudent && hasRotation && (
												<p className="text-xs text-muted-foreground">
													This will deactivate the
													student&apos;s current
													rotation and assign them to
													the selected department.
													Previous case progress is
													preserved.
												</p>
											)}
										</>
									)}

									{/* Adjust Day fields */}
									{assignMode === "adjust_day" &&
										isStudent &&
										hasRotation &&
										assignRotationInfo && (
											<div className="space-y-2">
												<Label htmlFor="adjust-total-day">
													Set total day to
												</Label>
												<div className="flex items-center gap-2">
													<Input
														id="adjust-total-day"
														type="number"
														min={0}
														max={
															assignRotationInfo.total
														}
														value={adjustTotalDay}
														onChange={(e) =>
															setAdjustTotalDay(
																Number(
																	e.target.value,
																),
															)
														}
														className="w-24"
													/>
													<span className="text-sm text-muted-foreground">
														of {assignRotationInfo.total}
													</span>
												</div>
											</div>
										)}

									<div className="flex justify-end gap-2">
										<Button
											type="button"
											variant="outline"
											onClick={() =>
												setIsAssignModalOpen(false)
											}
										>
											Cancel
										</Button>
										<Button
											type="submit"
											disabled={
												isAssignSubmitting ||
												(assignMode === "change_dept" &&
													!selectedDeptId)
											}
										>
											{isAssignSubmitting ? (
												<>
													<Loader2 className="mr-2 h-4 w-4 animate-spin" />
													Updating...
												</>
											) : (
												"Apply"
											)}
										</Button>
									</div>
								</form>
							)}
						</CardContent>
					</Card>
				</div>
			)}

			{/* Delete Confirmation Modal */}
			{isDeleteModalOpen && deleteTargetUser && (
				<div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
					<Card className="w-full max-w-md">
						<CardHeader>
							<CardTitle>Delete User — {deleteTargetUser.full_name}</CardTitle>
						</CardHeader>
						<CardContent>
							<p className="text-sm text-muted-foreground mb-4">
								Choose how to delete this user. This action cannot be undone.
							</p>
							<div className="space-y-3">
								<Button
									variant="outline"
									className="w-full justify-start"
									onClick={() => handleDelete("soft")}
									disabled={isDeleting}
								>
									<div className="text-left">
										<div className="font-medium">Deactivate (Soft Delete)</div>
										<div className="text-xs text-muted-foreground">
											User cannot login but data is preserved. Can be reactivated.
										</div>
									</div>
								</Button>
								<Button
									variant="destructive"
									className="w-full justify-start"
									onClick={() => handleDelete("hard")}
									disabled={isDeleting}
								>
									<div className="text-left">
										<div className="font-medium">Permanently Delete (Hard Delete)</div>
										<div className="text-xs">
											All personal data is anonymized. Submissions and logs are kept.
										</div>
									</div>
								</Button>
							</div>
							{isDeleting && (
								<div className="mt-3 flex items-center gap-2 text-sm text-muted-foreground">
									<Loader2 className="h-4 w-4 animate-spin" />
									Deleting...
								</div>
							)}
							<div className="mt-4 flex justify-end">
								<Button
									variant="outline"
									onClick={() => {
										setIsDeleteModalOpen(false);
										setDeleteTargetUser(null);
									}}
									disabled={isDeleting}
								>
									Cancel
								</Button>
							</div>
						</CardContent>
					</Card>
				</div>
			)}
		</div>
	);
}
