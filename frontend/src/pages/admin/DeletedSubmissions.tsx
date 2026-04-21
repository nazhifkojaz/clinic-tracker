import {
	AlertCircle,
	CheckCircle,
	ChevronLeft,
	ChevronRight,
	Clock,
	Eye,
	FileImage,
	Loader2,
	RotateCcw,
	Trash2,
	X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { TableSkeleton } from "@/components/skeletons/TableSkeleton";
import { submissionService } from "@/services/submissions";
import { departmentService } from "@/services/departments";
import type { DeletedSubmission, SubmissionStatus } from "@/types/submission";
import type { DepartmentWithCategories, TaskCategory } from "@/types/department";

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

export default function DeletedSubmissions() {
	const [submissions, setSubmissions] = useState<DeletedSubmission[]>([]);
	const [totalCount, setTotalCount] = useState(0);
	const [currentPage, setCurrentPage] = useState(0);
	const [hasMore, setHasMore] = useState(false);
	const [isLoading, setIsLoading] = useState(true);
	const [isDeptsLoading, setIsDeptsLoading] = useState(true);
	const [error, setError] = useState("");
	const [restoringId, setRestoringId] = useState<string | null>(null);

	// View modal state
	const [selectedSubmission, setSelectedSubmission] =
		useState<DeletedSubmission | null>(null);
	const [proofUrl, setProofUrl] = useState("");
	const [isProofLoading, setIsProofLoading] = useState(false);

	const [departments, setDepartments] = useState<DepartmentWithCategories[]>([]);

	useEffect(() => {
		departmentService
			.list()
			.then(async (depts) => {
				const withCats = await Promise.all(
					depts.map(async (dept) => {
						const categories = await departmentService.listCategories(dept.id);
						return { ...dept, task_categories: categories };
					}),
				);
				setDepartments(withCats);
			})
			.catch(() => {})
			.finally(() => setIsDeptsLoading(false));
	}, []);

	const categoriesMap = useMemo(() => {
		const map: Record<string, TaskCategory> = {};
		departments.forEach((dept) => {
			dept.task_categories.forEach((cat) => {
				map[cat.id] = cat;
			});
		});
		return map;
	}, [departments]);

	const departmentsMap = useMemo(() => {
		const map: Record<string, string> = {};
		departments.forEach((d) => {
			map[d.id] = d.name;
		});
		return map;
	}, [departments]);

	const fetchData = useCallback(async () => {
		try {
			setIsLoading(true);
			setError("");
			const response = await submissionService.listDeleted({
				limit: PAGE_SIZE,
				offset: currentPage * PAGE_SIZE,
			});
			setSubmissions(response.items);
			setTotalCount(response.total);
			setHasMore(response.has_more);
		} catch {
			setError("Failed to load deleted submissions");
		} finally {
			setIsLoading(false);
		}
	}, [currentPage]);

	useEffect(() => {
		fetchData();
	}, [fetchData]);

	const handleRestore = async (id: string) => {
		try {
			setRestoringId(id);
			await submissionService.restore(id);
			await fetchData();
		} catch {
			setError("Failed to restore submission");
		} finally {
			setRestoringId(null);
		}
	};

	const handleViewDetail = async (submission: DeletedSubmission) => {
		setSelectedSubmission(submission);
		setProofUrl("");
		setIsProofLoading(true);

		const requestedId = submission.id;
		try {
			const url = await submissionService.getDeletedProofUrl(requestedId);
			setSelectedSubmission((current) => {
				if (current?.id !== requestedId) return current;
				setProofUrl(url);
				return current;
			});
		} catch {
			setSelectedSubmission((current) => {
				if (current?.id !== requestedId) return current;
				setProofUrl("");
				return current;
			});
		} finally {
			setSelectedSubmission((current) => {
				if (current?.id !== requestedId) return current;
				setIsProofLoading(false);
				return current;
			});
		}
	};

	const handleCloseDetail = () => {
		setSelectedSubmission(null);
		setProofUrl("");
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

	return (
		<div className="space-y-6">
			<div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
				<div>
					<h1 className="flex items-center gap-2 text-2xl font-bold">
						<Trash2 className="h-6 w-6" />
						Deleted Submissions
					</h1>
					<p className="text-muted-foreground">
						Restore soft-deleted submissions. Only pending submissions can be
						deleted.
					</p>
				</div>
			</div>

			{error && (
				<div className="flex items-center gap-2 rounded-md bg-destructive/10 p-3 text-sm text-destructive">
					<AlertCircle className="h-4 w-4" />
					<span>{error}</span>
				</div>
			)}

			{isLoading || isDeptsLoading ? (
				<TableSkeleton rows={5} cols={7} />
			) : submissions.length === 0 ? (
				<div className="flex min-h-[300px] flex-col items-center justify-center text-center">
					<Trash2 className="mb-3 h-12 w-12 text-muted-foreground" />
					<h3 className="text-lg font-semibold">No deleted submissions</h3>
					<p className="text-sm text-muted-foreground">
						Deleted submissions will appear here.
					</p>
				</div>
			) : (
				<div className="overflow-x-auto rounded-lg border">
					<table className="w-full text-sm">
						<thead className="bg-muted/50">
							<tr>
								<th className="px-4 py-3 text-left font-medium">Deleted At</th>
								<th className="px-4 py-3 text-left font-medium">Student</th>
								<th className="px-4 py-3 text-left font-medium">Department</th>
								<th className="px-4 py-3 text-left font-medium">
									Task Category
								</th>
								<th className="px-4 py-3 text-left font-medium">Cases</th>
								<th className="px-4 py-3 text-left font-medium">Deleted By</th>
								<th className="px-4 py-3 text-left font-medium">Actions</th>
							</tr>
						</thead>
						<tbody className="divide-y">
							{submissions.map((sub) => (
								<tr key={sub.id} className="hover:bg-muted/30">
									<td className="px-4 py-3 text-muted-foreground">
										{sub.deleted_at
											? new Date(sub.deleted_at).toLocaleString()
											: "—"}
									</td>
									<td className="px-4 py-3">
										<div className="font-medium">
											{sub.student?.full_name || "Unknown"}
											{sub.student?.student_id && (
												<span className="font-normal text-muted-foreground">
													{" "}
													({sub.student.student_id})
												</span>
											)}
										</div>
										<div className="text-xs text-muted-foreground">
											{sub.student?.email}
										</div>
									</td>
									<td className="px-4 py-3">
										{departmentsMap[sub.department_id] || sub.department_id}
									</td>
									<td className="px-4 py-3">
										{categoriesMap[sub.task_category_id]?.name ||
											sub.task_category_id}
									</td>
									<td className="px-4 py-3">{sub.case_count}</td>
									<td className="px-4 py-3 text-muted-foreground">
										{sub.deleted_by_name || "—"}
									</td>
									<td className="px-4 py-3">
										<div className="flex items-center gap-1">
											<button
												onClick={() => handleViewDetail(sub)}
												className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium hover:bg-accent"
											>
												<Eye className="h-3 w-3" />
												View
											</button>
											<button
												onClick={() => handleRestore(sub.id)}
												disabled={restoringId === sub.id}
												className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-primary hover:bg-primary/10 disabled:cursor-not-allowed disabled:opacity-50"
											>
												{restoringId === sub.id ? (
													<Loader2 className="h-3 w-3 animate-spin" />
												) : (
													<RotateCcw className="h-3 w-3" />
												)}
												Restore
											</button>
										</div>
									</td>
								</tr>
							))}
						</tbody>
					</table>

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
									Page {currentPage + 1} of{" "}
									{Math.ceil(totalCount / PAGE_SIZE)}
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

			{/* View Detail Modal */}
			{selectedSubmission && (
				<div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
					<div className="max-h-[90vh] w-full max-w-2xl overflow-auto rounded-lg bg-card p-6 shadow-lg">
						<div className="flex items-start justify-between">
							<h2 className="text-lg font-semibold">Deleted Submission Details</h2>
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
										{departmentsMap[selectedSubmission.department_id] ||
											selectedSubmission.department_id}
									</span>
								</div>
								<div>
									<span className="text-muted-foreground">Task Category: </span>
									<span className="font-medium">
										{categoriesMap[selectedSubmission.task_category_id]?.name ||
											selectedSubmission.task_category_id}
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

							{/* Deletion details */}
							<div className="rounded-md bg-destructive/5 p-3">
								<p className="text-sm font-medium text-destructive">
									Deletion Information
								</p>
								<p className="text-xs text-muted-foreground">
									Deleted by: {selectedSubmission.deleted_by_name || "Unknown"}
								</p>
								<p className="text-xs text-muted-foreground">
									Deleted at:{" "}
									{selectedSubmission.deleted_at
										? new Date(selectedSubmission.deleted_at).toLocaleString()
										: "—"}
								</p>
							</div>

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
						</div>
					</div>
				</div>
			)}
		</div>
	);
}
