import {
	AlertCircle,
	CheckCircle,
	ChevronLeft,
	ChevronRight,
	Clock,
	Eye,
	FileImage,
	Loader2,
	Pencil,
	ThumbsDown,
	ThumbsUp,
	Trash2,
	Upload,
	X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { MAX_PROOF_FILE_SIZE } from "@/lib/constants";
import { TableSkeleton } from "@/components/skeletons/TableSkeleton";
import { departmentService } from "@/services/departments";
import { submissionService } from "@/services/submissions";
import { useAuthStore } from "@/stores/authStore";
import type {
	DepartmentWithCategories,
	TaskCategory,
} from "@/types/department";
import type { Submission, SubmissionStatus, SubmissionUpdate } from "@/types/submission";

const statusConfig: Record<
	SubmissionStatus,
	{ label: string; className: string }
> = {
	pending: {
		label: "Pending",
		className: "bg-yellow-500/10 text-yellow-600 dark:text-yellow-400",
	},
	approved: {
		label: "Approved",
		className: "bg-green-500/10 text-green-600 dark:text-green-400",
	},
	rejected: {
		label: "Rejected",
		className: "bg-red-500/10 text-red-600 dark:text-red-400",
	},
};

const PAGE_SIZE = 20;

export default function SubmissionHistory() {
	const { user } = useAuthStore();
	const navigate = useNavigate();
	const isStudent = user?.role === "student";

	const [submissions, setSubmissions] = useState<Submission[]>([]);
	const [totalCount, setTotalCount] = useState(0);
	const [currentPage, setCurrentPage] = useState(0);
	const [hasMore, setHasMore] = useState(false);

	const [departments, setDepartments] = useState<DepartmentWithCategories[]>(
		[],
	);
	const [isLoading, setIsLoading] = useState(true);
	const [isDeptsLoading, setIsDeptsLoading] = useState(true);
	const [error, setError] = useState("");

	// Detail modal state
	const [selectedSubmission, setSelectedSubmission] =
		useState<Submission | null>(null);
	const [proofUrl, setProofUrl] = useState("");
	const [isProofLoading, setIsProofLoading] = useState(false);

	// Filters (supervisor only)
	const [statusFilter, setStatusFilter] = useState<string>("");
	const [departmentFilter, setDepartmentFilter] = useState<string>("");

	// Review state (supervisor only)
	const [isReviewing, setIsReviewing] = useState(false);
	const [reviewNotes, setReviewNotes] = useState("");

	// Delete state
	const [deletingId, setDeletingId] = useState<string | null>(null);

	// Edit modal state
	const [editingSubmission, setEditingSubmission] = useState<Submission | null>(null);
	const [editCaseCount, setEditCaseCount] = useState(1);
	const [editNotes, setEditNotes] = useState("");
	const [editImageFile, setEditImageFile] = useState<File | null>(null);
	const [editImagePreview, setEditImagePreview] = useState("");
	const [editUploadedObjectKey, setEditUploadedObjectKey] = useState("");
	const [isEditUploading, setIsEditUploading] = useState(false);
	const [isEditSubmitting, setIsEditSubmitting] = useState(false);

	// Fetch departments and categories once on mount (independent of filters)
	useEffect(() => {
		const fetchCategories = async () => {
			try {
				const deptsData = await departmentService.list();
				const activeDepts = deptsData.filter((d) => d.is_active);

				const deptsWithCategories: DepartmentWithCategories[] =
					await Promise.all(
						activeDepts.map(async (dept) => {
							const categories = await departmentService.listCategories(
								dept.id,
							);
							return {
								...dept,
								task_categories: categories,
							};
						}),
					);

				setDepartments(deptsWithCategories);
			} catch {
				setError("Failed to load departments");
			} finally {
				setIsDeptsLoading(false);
			}
		};

		fetchCategories();
	}, []); // Empty deps - only runs once on mount

	// Derive categories map from departments (no separate state needed)
	const categoriesMap = useMemo(() => {
		const map: Record<string, TaskCategory> = {};
		departments.forEach((dept) => {
			dept.task_categories.forEach((cat) => {
				map[cat.id] = cat;
			});
		});
		return map;
	}, [departments]);

	// O(1) department name lookup map
	const departmentsMap = useMemo(() => {
		const map: Record<string, string> = {};
		departments.forEach((d) => {
			map[d.id] = d.name;
		});
		return map;
	}, [departments]);

	// Fetch submissions when filters or page changes
	const fetchData = useCallback(async () => {
		try {
			setIsLoading(true);
			setError("");

			const params: {
				department_id?: string;
				status?: string;
				limit: number;
				offset: number;
			} = {
				limit: PAGE_SIZE,
				offset: currentPage * PAGE_SIZE,
			};
			if (departmentFilter) params.department_id = departmentFilter;
			if (statusFilter) params.status = statusFilter;

			const response = await submissionService.list(params);
			setSubmissions(response.items);
			setTotalCount(response.total);
			setHasMore(response.has_more);
		} catch {
			setError("Failed to load submissions");
		} finally {
			setIsLoading(false);
		}
	}, [departmentFilter, statusFilter, currentPage]);

	useEffect(() => {
		fetchData();
	}, [fetchData]);

	// Reset to first page when filters change
	useEffect(() => {
		setCurrentPage(0);
	}, [departmentFilter, statusFilter]);

	const handleViewDetail = async (submission: Submission) => {
		setSelectedSubmission(submission);
		setProofUrl("");
		setIsProofLoading(true);

		try {
			const url = await submissionService.getProofUrl(submission.id);
			setProofUrl(url);
		} catch {
			setError("Failed to load proof image");
		} finally {
			setIsProofLoading(false);
		}
	};

	const handleCloseDetail = () => {
		setSelectedSubmission(null);
		setProofUrl("");
		setReviewNotes("");
		setIsReviewing(false);
	};

	const handleDelete = async (id: string) => {
		if (!window.confirm("Are you sure you want to delete this submission? This action cannot be undone.")) {
			return;
		}
		try {
			setDeletingId(id);
			await submissionService.delete(id);
			await fetchData();
		} catch {
			setError("Failed to delete submission");
		} finally {
			setDeletingId(null);
		}
	};

	const handleReview = async (status: "approved" | "rejected") => {
		if (!selectedSubmission) return;

		try {
			setIsReviewing(true);
			await submissionService.review(selectedSubmission.id, {
				status,
				review_notes: reviewNotes || null,
			});
			await fetchData(); // Refresh list
			handleCloseDetail();
		} catch {
			setError("Failed to review submission");
		} finally {
			setIsReviewing(false);
		}
	};

	const handleOpenEdit = (sub: Submission) => {
		setEditingSubmission(sub);
		setEditCaseCount(sub.case_count);
		setEditNotes(sub.notes || "");
		setEditImageFile(null);
		setEditImagePreview("");
		setEditUploadedObjectKey("");
	};

	const handleCloseEdit = () => {
		if (editImagePreview) URL.revokeObjectURL(editImagePreview);
		setEditingSubmission(null);
		setEditImageFile(null);
		setEditImagePreview("");
		setEditUploadedObjectKey("");
	};

	const handleEditImageSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
		const file = e.target.files?.[0];
		if (!file) return;

		if (file.size > MAX_PROOF_FILE_SIZE) {
			setError("Image file must be less than 5MB");
			return;
		}

		if (!file.type.startsWith("image/")) {
			setError("Please select an image file");
			return;
		}

		setEditImageFile(file);
		setError("");

		const previewUrl = URL.createObjectURL(file);
		setEditImagePreview(previewUrl);

		try {
			setIsEditUploading(true);

			const uploadData = await submissionService.getUploadUrl({
				filename: file.name,
				content_type: file.type,
			});

			const uploadResponse = await fetch(uploadData.upload_url, {
				method: "PUT",
				body: file,
				headers: { "Content-Type": file.type },
			});

			if (!uploadResponse.ok) throw new Error("Failed to upload image");

			setEditUploadedObjectKey(uploadData.object_key);
		} catch {
			setError("Failed to upload image. Please try again.");
			setEditImageFile(null);
			URL.revokeObjectURL(previewUrl);
			setEditImagePreview("");
			setEditUploadedObjectKey("");
		} finally {
			setIsEditUploading(false);
		}
	};

	const handleEditSubmit = async () => {
		if (!editingSubmission) return;

		try {
			setIsEditSubmitting(true);
			const update: SubmissionUpdate = {
				case_count: editCaseCount,
				notes: editNotes || null,
			};
			if (editUploadedObjectKey) {
				update.proof_key = editUploadedObjectKey;
			}
			await submissionService.update(editingSubmission.id, update);
			await fetchData();
			handleCloseEdit();
		} catch {
			setError("Failed to update submission");
		} finally {
			setIsEditSubmitting(false);
		}
	};

	const getStatusBadge = (status: SubmissionStatus) => {
		const config = statusConfig[status];
		return (
			<span
				className={`inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs font-medium ${config.className}`}
			>
				{status === "pending" && <Clock className="h-3 w-3" />}
				{status === "approved" && <CheckCircle className="h-3 w-3" />}
				{status === "rejected" && <X className="h-3 w-3" />}
				{config.label}
			</span>
		);
	};

	// Resolve names from IDs
	const getDepartmentName = (id: string) => departmentsMap[id] || id;

	const getTaskCategoryName = (id: string) => {
		const cat = categoriesMap[id];
		return cat?.name || id;
	};

	return (
		<div className="space-y-6">
			<div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
				<div>
					<h1 className="text-2xl font-bold">
						{isStudent ? "My Submissions" : "All Submissions"}
					</h1>
					<p className="text-muted-foreground">
						{isStudent
							? "View your case submission history and review status."
							: "Review and manage student case submissions."}
					</p>
				</div>
			</div>

			{/* Filters - Supervisor only */}
			{!isStudent && (
				<div className="flex flex-wrap gap-3">
					<select
						value={departmentFilter}
						onChange={(e) => setDepartmentFilter(e.target.value)}
						className="rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
					>
						<option value="">All Departments</option>
						{departments.map((dept) => (
							<option key={dept.id} value={dept.id}>
								{dept.name}
							</option>
						))}
					</select>

					<select
						value={statusFilter}
						onChange={(e) => setStatusFilter(e.target.value)}
						className="rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
					>
						<option value="">All Status</option>
						<option value="pending">Pending</option>
						<option value="approved">Approved</option>
						<option value="rejected">Rejected</option>
					</select>
				</div>
			)}

			{error && (
				<div className="flex items-center gap-2 rounded-md bg-destructive/10 p-3 text-sm text-destructive">
					<AlertCircle className="h-4 w-4" />
					<span>{error}</span>
				</div>
			)}

			{isLoading || isDeptsLoading ? (
				<TableSkeleton rows={5} cols={6} />
			) : submissions.length === 0 ? (
				<div className="flex min-h-[300px] flex-col items-center justify-center text-center">
					<FileImage className="mb-3 h-12 w-12 text-muted-foreground" />
					<h3 className="text-lg font-semibold">No submissions found</h3>
					<p className="text-sm text-muted-foreground">
						{isStudent
							? "You haven't submitted any cases yet."
							: "No submissions match the current filters."}
					</p>
					{isStudent && (
						<button
							onClick={() => navigate("/cases/new")}
							className="mt-4 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
						>
							Submit Your First Case
						</button>
					)}
				</div>
			) : (
				<div className="overflow-x-auto rounded-lg border">
					<table className="w-full text-sm">
						<thead className="bg-muted/50">
							<tr>
								{!isStudent && (
									<th className="px-4 py-3 text-left font-medium">Student</th>
								)}
								<th className="px-4 py-3 text-left font-medium">Date</th>
								<th className="px-4 py-3 text-left font-medium">Department</th>
								<th className="px-4 py-3 text-left font-medium">
									Task Category
								</th>
								<th className="px-4 py-3 text-left font-medium">Cases</th>
								<th className="px-4 py-3 text-left font-medium">Assigned Reviewer</th>
								<th className="px-4 py-3 text-left font-medium">Status</th>
								<th className="px-4 py-3 text-left font-medium">Actions</th>
							</tr>
						</thead>
						<tbody className="divide-y">
							{submissions.map((sub) => (
								<tr key={sub.id} className="hover:bg-muted/30">
									{!isStudent && (
										<td className="px-4 py-3">
											<div className="font-medium">
												{sub.student?.full_name || "Unknown"}
												{sub.student?.student_id && (
													<span className="text-muted-foreground font-normal">
														{" "}
														({sub.student.student_id})
													</span>
												)}
											</div>
											<div className="text-xs text-muted-foreground">
												{sub.student?.email}
											</div>
										</td>
									)}
									<td className="px-4 py-3">
										{new Date(sub.created_at).toLocaleDateString()}
									</td>
									<td className="px-4 py-3">
										{getDepartmentName(sub.department_id)}
									</td>
									<td className="px-4 py-3">
										{getTaskCategoryName(sub.task_category_id)}
									</td>
									<td className="px-4 py-3">{sub.case_count}</td>
									<td className="px-4 py-3">
										{sub.target_supervisor?.full_name ? (
											<span className="font-medium">{sub.target_supervisor.full_name}</span>
										) : (
											<span className="text-muted-foreground">—</span>
										)}
									</td>
									<td className="px-4 py-3">{getStatusBadge(sub.status)}</td>
									<td className="px-4 py-3">
										<div className="flex items-center gap-1">
											<button
												onClick={() => handleViewDetail(sub)}
												className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium hover:bg-accent"
											>
												<Eye className="h-3 w-3" />
												View
											</button>
											{isStudent && sub.status === "pending" && (
												<button
													onClick={() => handleOpenEdit(sub)}
													className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium hover:bg-accent"
												>
													<Pencil className="h-3 w-3" />
													Edit
												</button>
											)}
											{sub.status === "pending" && (
												<button
													onClick={() => handleDelete(sub.id)}
													disabled={deletingId === sub.id}
													className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-destructive hover:bg-destructive/10 disabled:cursor-not-allowed disabled:opacity-50"
												>
													{deletingId === sub.id ? (
														<Loader2 className="h-3 w-3 animate-spin" />
													) : (
														<Trash2 className="h-3 w-3" />
													)}
													Delete
												</button>
											)}
										</div>
									</td>
								</tr>
							))}
						</tbody>
					</table>

					{/* Pagination Controls */}
					{totalCount > 0 && (
						<div className="flex items-center justify-between border-t px-4 py-3">
							<div className="text-sm text-muted-foreground">
								Showing {currentPage * PAGE_SIZE + 1} -{" "}
								{Math.min((currentPage + 1) * PAGE_SIZE, totalCount)} of{" "}
								{totalCount}
							</div>
							<div className="flex items-center gap-2">
								<button
									onClick={() => setCurrentPage((p) => Math.max(0, p - 1))}
									disabled={currentPage === 0 || isLoading}
									className="inline-flex items-center gap-1 rounded-md border px-3 py-2 text-sm font-medium hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
								>
									<ChevronLeft className="h-4 w-4" />
									Previous
								</button>
								<span className="text-sm">
									Page {currentPage + 1} of {Math.ceil(totalCount / PAGE_SIZE)}
								</span>
								<button
									onClick={() => setCurrentPage((p) => p + 1)}
									disabled={!hasMore || isLoading}
									className="inline-flex items-center gap-1 rounded-md border px-3 py-2 text-sm font-medium hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
								>
									Next
									<ChevronRight className="h-4 w-4" />
								</button>
							</div>
						</div>
					)}
				</div>
			)}

			{/* Detail Modal */}
			{selectedSubmission && (
				<div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
					<div className="max-h-[90vh] w-full max-w-2xl overflow-auto rounded-lg bg-card p-6 shadow-lg">
						<div className="flex items-start justify-between">
							<h2 className="text-lg font-semibold">Submission Details</h2>
							<button
								onClick={handleCloseDetail}
								className="rounded-full p-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
							>
								<X className="h-5 w-5" />
							</button>
						</div>

						<div className="mt-4 space-y-4">
							{/* Status */}
							<div className="flex items-center justify-between">
								<span className="text-sm text-muted-foreground">Status</span>
								{getStatusBadge(selectedSubmission.status)}
							</div>

							{/* Details */}
							<div className="grid grid-cols-2 gap-4 text-sm">
								<div>
									<span className="text-muted-foreground">Department: </span>
									<span className="font-medium">
										{getDepartmentName(selectedSubmission.department_id)}
									</span>
								</div>
								<div>
									<span className="text-muted-foreground">Task Category: </span>
									<span className="font-medium">
										{getTaskCategoryName(selectedSubmission.task_category_id)}
									</span>
								</div>
								<div>
									<span className="text-muted-foreground">Case Count: </span>
									<span className="font-medium">
										{selectedSubmission.case_count}
									</span>
								</div>
								<div>
									<span className="text-muted-foreground">Submitted: </span>
									<span className="font-medium">
										{new Date(selectedSubmission.created_at).toLocaleString()}
									</span>
								</div>
								<div>
									<span className="text-muted-foreground">Assigned Reviewer: </span>
									<span className="font-medium">
										{selectedSubmission.target_supervisor?.full_name || "—"}
									</span>
								</div>
							</div>

							{/* Notes */}
							{selectedSubmission.notes && (
								<div>
									<span className="text-sm text-muted-foreground">Notes: </span>
									<p className="mt-1 rounded-md bg-muted/50 p-2 text-sm">
										{selectedSubmission.notes}
									</p>
								</div>
							)}

							{/* Review info (if reviewed) */}
							{(selectedSubmission.reviewed_by ||
								selectedSubmission.review_notes) && (
								<div className="rounded-md bg-muted/50 p-3">
									<p className="text-sm font-medium">Review Information</p>
									<p className="text-xs text-muted-foreground">
										Reviewed by:{" "}
										{selectedSubmission.reviewer?.full_name || "Unknown"}
									</p>
									{selectedSubmission.review_notes && (
										<p className="mt-1 text-sm">
											{selectedSubmission.review_notes}
										</p>
									)}
								</div>
							)}

							{/* Proof Image */}
							<div>
								<span className="text-sm font-medium">Proof Image</span>
								<div className="mt-2 rounded-lg border bg-muted/20 p-4">
									{isProofLoading ? (
										<div className="flex h-48 items-center justify-center">
											<Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
										</div>
									) : proofUrl ? (
										proofUrl.startsWith("mock://") ? (
											<div className="flex h-48 items-center justify-center text-center">
												<div>
													<FileImage className="mx-auto mb-2 h-10 w-10 text-muted-foreground" />
													<p className="text-sm text-muted-foreground">
														Mock mode - R2 not configured
													</p>
												</div>
											</div>
										) : (
											<img
												src={proofUrl}
												alt="Proof"
												loading="lazy"
												decoding="async"
												className="mx-auto max-h-96 rounded-md object-contain"
											/>
										)
									) : (
										<div className="flex h-48 items-center justify-center text-center">
											<p className="text-sm text-muted-foreground">
												Failed to load proof image
											</p>
										</div>
									)}
								</div>
							</div>

							{/* Review Actions - target supervisor only */}
							{selectedSubmission.can_review && selectedSubmission.status === "pending" && (
								<div className="space-y-3 border-t pt-4">
									<span className="text-sm font-medium">Review Action</span>
									<textarea
										value={reviewNotes}
										onChange={(e) => setReviewNotes(e.target.value)}
										placeholder="Add review notes (optional)..."
										rows={2}
										className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
									/>
									<div className="flex gap-3">
										<button
											onClick={() => handleReview("approved")}
											disabled={isReviewing}
											className="flex flex-1 items-center justify-center gap-2 rounded-md bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:cursor-not-allowed disabled:opacity-50"
										>
											{isReviewing ? (
												<Loader2 className="h-4 w-4 animate-spin" />
											) : (
												<ThumbsUp className="h-4 w-4" />
											)}
											Approve
										</button>
										<button
											onClick={() => handleReview("rejected")}
											disabled={isReviewing}
											className="flex flex-1 items-center justify-center gap-2 rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50"
										>
											{isReviewing ? (
												<Loader2 className="h-4 w-4 animate-spin" />
											) : (
												<ThumbsDown className="h-4 w-4" />
											)}
											Reject
										</button>
									</div>
								</div>
							)}
						</div>
					</div>
				</div>
			)}

			{/* Edit Modal */}
			{editingSubmission && (
				<div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
					<div className="max-h-[90vh] w-full max-w-lg overflow-auto rounded-lg bg-card p-6 shadow-lg">
						<div className="flex items-start justify-between">
							<h2 className="text-lg font-semibold">Edit Submission</h2>
							<button
								onClick={handleCloseEdit}
								className="rounded-full p-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
							>
								<X className="h-5 w-5" />
							</button>
						</div>

						<div className="mt-4 space-y-4">
							{/* Read-only info */}
							<div className="rounded-md bg-muted/50 p-3 text-sm space-y-1">
								<div>
									<span className="text-muted-foreground">Department: </span>
									<span className="font-medium">{getDepartmentName(editingSubmission.department_id)}</span>
								</div>
								<div>
									<span className="text-muted-foreground">Task Category: </span>
									<span className="font-medium">{getTaskCategoryName(editingSubmission.task_category_id)}</span>
								</div>
								<div>
									<span className="text-muted-foreground">Assigned Reviewer: </span>
									<span className="font-medium">{editingSubmission.target_supervisor?.full_name || "—"}</span>
								</div>
							</div>

							{/* Editable: Case Count */}
							<div className="space-y-1">
								<label htmlFor="editCaseCount" className="text-sm font-medium">
									Number of Cases <span className="text-destructive">*</span>
								</label>
								<input
									id="editCaseCount"
									type="number"
									min="1"
									value={editCaseCount}
									onChange={(e) =>
										setEditCaseCount(Math.max(1, parseInt(e.target.value) || 1))
									}
									className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
								/>
							</div>

							{/* Editable: Proof Image */}
							<div className="space-y-1">
								<label className="text-sm font-medium">Proof Image</label>
								{editImagePreview ? (
									<div className="relative rounded-lg border bg-muted/20 p-3">
										<div className="flex items-center gap-3">
											<img
												src={editImagePreview}
												alt="New proof preview"
												className="h-16 w-16 rounded-md object-cover"
											/>
											<div className="flex-1 text-sm">
												<p className="font-medium">{editImageFile?.name}</p>
												{editUploadedObjectKey ? (
													<p className="flex items-center gap-1 text-xs text-green-600 dark:text-green-400">
														<CheckCircle className="h-3 w-3" />
														Uploaded successfully
													</p>
												) : isEditUploading ? (
													<p className="flex items-center gap-1 text-xs text-muted-foreground">
														<Loader2 className="h-3 w-3 animate-spin" />
														Uploading...
													</p>
												) : null}
											</div>
											<button
												type="button"
												onClick={() => {
													if (editImagePreview) URL.revokeObjectURL(editImagePreview);
													setEditImageFile(null);
													setEditImagePreview("");
													setEditUploadedObjectKey("");
												}}
												className="rounded-full p-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
											>
												<X className="h-4 w-4" />
											</button>
										</div>
									</div>
								) : (
									<div className="rounded-md border border-dashed border-input bg-muted/20 p-3 text-sm text-muted-foreground">
										<p>Current proof image on file. Upload a new one to replace it.</p>
										<label className="mt-2 inline-flex cursor-pointer items-center gap-2 rounded-md border px-3 py-1.5 text-xs font-medium hover:bg-accent">
											<Upload className="h-3 w-3" />
											Replace Image
											<input
												type="file"
												accept="image/jpeg,image/png,image/gif,image/webp"
												onChange={handleEditImageSelect}
												disabled={isEditUploading}
												className="hidden"
											/>
										</label>
									</div>
								)}
							</div>

							{/* Editable: Notes */}
							<div className="space-y-1">
								<label htmlFor="editNotes" className="text-sm font-medium">
									Notes <span className="text-muted-foreground">(optional)</span>
								</label>
								<textarea
									id="editNotes"
									value={editNotes}
									onChange={(e) => setEditNotes(e.target.value)}
									rows={3}
									placeholder="Add any additional notes..."
									className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
								/>
							</div>

							<div className="flex justify-end gap-3 border-t pt-4">
								<button
									onClick={handleCloseEdit}
									className="rounded-md border border-input px-4 py-2 text-sm font-medium hover:bg-accent"
								>
									Cancel
								</button>
								<button
									onClick={handleEditSubmit}
									disabled={isEditSubmitting || isEditUploading || editCaseCount < 1}
									className="flex min-w-[100px] items-center justify-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
								>
									{isEditSubmitting ? (
										<>
											<Loader2 className="h-4 w-4 animate-spin" />
											Saving...
										</>
									) : (
										"Save Changes"
									)}
								</button>
							</div>
						</div>
					</div>
				</div>
			)}
		</div>
	);
}
