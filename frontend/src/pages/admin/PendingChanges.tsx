import {
	Check,
	ChevronLeft,
	ChevronRight,
	Loader2,
	X,
} from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { departmentService } from "@/services/departments";
import { userService } from "@/services/users";
import type {
	PendingChangeStatus,
	PendingChangeWithUser,
} from "@/types/user";

const PAGE_SIZE = 25;

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
	remove_student_id: "Remove Student",
};

interface LookupMaps {
	departments: Map<string, string>;
	supervisors: Map<string, string>;
	students: Map<string, string>;
}

function resolveValue(
	fieldName: string,
	value: string | null,
	lookups: LookupMaps,
): string {
	if (!value) return "—";
	switch (fieldName) {
		case "department_id":
			return lookups.departments.get(value) ?? value;
		case "supervisor_id":
			return lookups.supervisors.get(value) ?? value;
		case "remove_student_id":
			return lookups.students.get(value) ?? value;
		default:
			return value;
	}
}

export default function PendingChanges() {
	const [changes, setChanges] = useState<PendingChangeWithUser[]>([]);
	const [totalCount, setTotalCount] = useState(0);
	const [currentPage, setCurrentPage] = useState(0);
	const [hasMore, setHasMore] = useState(false);
	const [isLoading, setIsLoading] = useState(false);
	const [statusFilter, setStatusFilter] = useState<PendingChangeStatus | "">("");
	const [actioningId, setActioningId] = useState<string | null>(null);

	const [lookups, setLookups] = useState<LookupMaps>({
		departments: new Map(),
		supervisors: new Map(),
		students: new Map(),
	});

	useEffect(() => {
		Promise.all([
			departmentService
				.list()
				.then((depts) =>
					new Map(depts.map((d) => [d.id, d.name])),
				),
			userService
				.list({ role: "supervisor", is_active: true, limit: 200 })
				.then((res) =>
					new Map(res.items.map((u) => [u.id, u.full_name])),
				),
			userService
				.list({ role: "student", is_active: true, limit: 200 })
				.then((res) =>
					new Map(res.items.map((u) => [u.id, u.full_name])),
				),
		])
			.then(([departments, supervisors, students]) =>
				setLookups({ departments, supervisors, students }),
			)
			.catch(() => {});
	}, []);

	const fetchChanges = async (
		page: number = currentPage,
		status?: PendingChangeStatus | "",
	) => {
		try {
			setIsLoading(true);
			const params: Record<string, unknown> = {
				limit: PAGE_SIZE,
				offset: page * PAGE_SIZE,
			};
			if (status) params.status = status;
			const response = await userService.listPendingChanges(params);
			setChanges(response.items);
			setTotalCount(response.total);
			setHasMore(response.has_more);
		} catch {
			toast.error("Failed to load pending changes");
		} finally {
			setIsLoading(false);
		}
	};

	useEffect(() => {
		fetchChanges(0, statusFilter);
		setCurrentPage(0);
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [statusFilter]);

	const handlePageChange = (newPage: number) => {
		setCurrentPage(newPage);
		fetchChanges(newPage, statusFilter);
	};

	const handleApprove = async (changeId: string) => {
		setActioningId(changeId);
		try {
			await userService.approvePendingChange(changeId);
			toast.success("Change approved and applied");
			fetchChanges(currentPage, statusFilter);
		} catch {
			toast.error("Failed to approve change");
		} finally {
			setActioningId(null);
		}
	};

	const handleReject = async (changeId: string) => {
		setActioningId(changeId);
		try {
			await userService.rejectPendingChange(changeId);
			toast.success("Change rejected");
			fetchChanges(currentPage, statusFilter);
		} catch {
			toast.error("Failed to reject change");
		} finally {
			setActioningId(null);
		}
	};

	return (
		<div className="space-y-6">
			<div className="flex items-center justify-between">
				<h1 className="text-2xl font-bold">Pending Profile Changes</h1>
				<select
					className="rounded-md border border-input bg-background px-3 py-2 text-sm"
					value={statusFilter}
					onChange={(e) =>
						setStatusFilter(
							(e.target.value as PendingChangeStatus | "") || "",
						)
					}
				>
					<option value="">All statuses</option>
					<option value="pending">Pending</option>
					<option value="approved">Approved</option>
					<option value="rejected">Rejected</option>
				</select>
			</div>

			<Card>
				<CardContent className="p-0">
					{isLoading && changes.length === 0 ? (
						<div className="flex items-center justify-center py-12">
							<Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
						</div>
					) : changes.length === 0 ? (
						<div className="py-12 text-center text-muted-foreground">
							No profile change requests found.
						</div>
					) : (
						<div className="overflow-x-auto">
							<table className="w-full min-w-[800px]">
								<thead>
									<tr className="border-b text-left text-sm text-muted-foreground">
										<th className="p-4">User</th>
										<th className="p-4">Email</th>
										<th className="p-4">Field</th>
										<th className="p-4">Current</th>
										<th className="p-4">Requested</th>
										<th className="p-4">Reason</th>
										<th className="p-4">Status</th>
										<th className="p-4">Submitted</th>
										<th className="p-4">Actions</th>
									</tr>
								</thead>
								<tbody>
									{changes.map((change) => (
										<tr key={change.id} className="border-b last:border-0">
											<td className="p-4 font-medium">
												{change.user_name}
											</td>
											<td className="p-4 text-muted-foreground">
												{change.user_email}
											</td>
											<td className="p-4">
												{fieldLabels[change.field_name] ||
													change.field_name}
											</td>
											<td className="p-4 text-muted-foreground">
												{resolveValue(
													change.field_name,
													change.old_value,
													lookups,
												)}
											</td>
											<td className="p-4">
												{resolveValue(
													change.field_name,
													change.new_value,
													lookups,
												)}
											</td>
											<td className="p-4 text-sm text-muted-foreground">
												{change.reason || "—"}
											</td>
											<td className="p-4">
												<span
													className={`rounded-full px-2 py-1 text-xs font-medium capitalize ${statusBadgeColor[change.status]}`}
												>
													{change.status}
												</span>
											</td>
											<td className="p-4 text-sm text-muted-foreground">
												{new Date(
													change.created_at,
												).toLocaleDateString()}
											</td>
											<td className="p-4">
												{change.status === "pending" ? (
													<div className="flex items-center gap-1">
														<Button
															size="sm"
															onClick={() =>
																handleApprove(change.id)
															}
															disabled={
																actioningId === change.id
															}
														>
															{actioningId === change.id ? (
																<Loader2 className="mr-1 h-3 w-3 animate-spin" />
															) : (
																<Check className="mr-1 h-3 w-3" />
															)}
															Approve
														</Button>
														<Button
															size="sm"
															variant="destructive"
															onClick={() =>
																handleReject(change.id)
															}
															disabled={
																actioningId === change.id
															}
														>
															{actioningId === change.id ? (
																<Loader2 className="mr-1 h-3 w-3 animate-spin" />
															) : (
																<X className="mr-1 h-3 w-3" />
															)}
															Reject
														</Button>
													</div>
												) : (
													<span className="text-sm text-muted-foreground">
														Reviewed
													</span>
												)}
											</td>
										</tr>
									))}
								</tbody>
							</table>
						</div>
					)}

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
		</div>
	);
}
