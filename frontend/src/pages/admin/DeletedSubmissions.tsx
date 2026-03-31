import {
	AlertCircle,
	ChevronLeft,
	ChevronRight,
	RotateCcw,
	Trash2,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { TableSkeleton } from "@/components/skeletons/TableSkeleton";
import { submissionService } from "@/services/submissions";
import { departmentService } from "@/services/departments";
import type { DeletedSubmission } from "@/types/submission";
import type { DepartmentWithCategories, TaskCategory } from "@/types/department";
import { Loader2 } from "lucide-react";

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
		</div>
	);
}
