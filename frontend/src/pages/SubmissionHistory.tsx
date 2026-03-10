import { useCallback, useEffect, useState } from "react";
import { useAuthStore } from "@/stores/authStore";
import { submissionService } from "@/services/submissions";
import { departmentService } from "@/services/departments";
import type { Submission, SubmissionStatus } from "@/types/submission";
import type { DepartmentWithCategories, TaskCategory } from "@/types/department";
import {
  AlertCircle,
  CheckCircle,
  Clock,
  Eye,
  FileImage,
  Loader2,
  ThumbsDown,
  ThumbsUp,
  X,
} from "lucide-react";

const statusConfig: Record<
  SubmissionStatus,
  { label: string; className: string }
> = {
  pending: { label: "Pending", className: "bg-yellow-500/10 text-yellow-600 dark:text-yellow-400" },
  approved: { label: "Approved", className: "bg-green-500/10 text-green-600 dark:text-green-400" },
  rejected: { label: "Rejected", className: "bg-red-500/10 text-red-600 dark:text-red-400" },
};

export default function SubmissionHistory() {
  const { user } = useAuthStore();
  const isStudent = user?.role === "student";

  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [departments, setDepartments] = useState<DepartmentWithCategories[]>([]);
  const [categoriesMap, setCategoriesMap] = useState<Record<string, TaskCategory>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  // Detail modal state
  const [selectedSubmission, setSelectedSubmission] = useState<Submission | null>(null);
  const [proofUrl, setProofUrl] = useState("");
  const [isProofLoading, setIsProofLoading] = useState(false);

  // Filters (supervisor only)
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [departmentFilter, setDepartmentFilter] = useState<string>("");

  // Review state (supervisor only)
  const [isReviewing, setIsReviewing] = useState(false);
  const [reviewNotes, setReviewNotes] = useState("");

  const fetchData = useCallback(async () => {
    try {
      setIsLoading(true);
      setError("");

      const params: { department_id?: string; status?: string } = {};
      if (departmentFilter) params.department_id = departmentFilter;
      if (statusFilter) params.status = statusFilter;

      const [subsData, deptsData] = await Promise.all([
        submissionService.list(params),
        departmentService.list(),
      ]);

      setSubmissions(subsData);
      const activeDepts = deptsData.filter((d) => d.is_active);

      // Fetch categories for each department
      const deptsWithCategories: DepartmentWithCategories[] = await Promise.all(
        activeDepts.map(async (dept) => {
          const categories = await departmentService.listCategories(dept.id);
          return {
            ...dept,
            task_categories: categories,
          };
        })
      );

      setDepartments(deptsWithCategories);

      // Build a categories map for easy lookup
      const catsMap: Record<string, TaskCategory> = {};
      deptsWithCategories.forEach((dept) => {
        dept.task_categories.forEach((cat) => {
          catsMap[cat.id] = cat;
        });
      });
      setCategoriesMap(catsMap);
    } catch {
      setError("Failed to load submissions");
    } finally {
      setIsLoading(false);
    }
  }, [departmentFilter, statusFilter]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

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

  const getStatusBadge = (status: SubmissionStatus) => {
    const config = statusConfig[status];
    return (
      <span className={`inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs font-medium ${config.className}`}>
        {status === "pending" && <Clock className="h-3 w-3" />}
        {status === "approved" && <CheckCircle className="h-3 w-3" />}
        {status === "rejected" && <X className="h-3 w-3" />}
        {config.label}
      </span>
    );
  };

  // Resolve names from IDs
  const getDepartmentName = (id: string) => {
    const dept = departments.find((d) => d.id === id);
    return dept?.name || id;
  };

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

      {isLoading ? (
        <div className="flex min-h-[300px] items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
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
              onClick={() => (window.location.hash = "#/cases/new")}
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
                {!isStudent && <th className="px-4 py-3 text-left font-medium">Student</th>}
                <th className="px-4 py-3 text-left font-medium">Date</th>
                <th className="px-4 py-3 text-left font-medium">Department</th>
                <th className="px-4 py-3 text-left font-medium">Task Category</th>
                <th className="px-4 py-3 text-left font-medium">Cases</th>
                <th className="px-4 py-3 text-left font-medium">Status</th>
                <th className="px-4 py-3 text-left font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {submissions.map((sub) => (
                <tr key={sub.id} className="hover:bg-muted/30">
                  {!isStudent && (
                    <td className="px-4 py-3">
                      <div className="font-medium">{sub.student_id}</div>
                    </td>
                  )}
                  <td className="px-4 py-3">
                    {new Date(sub.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3">{getDepartmentName(sub.department_id)}</td>
                  <td className="px-4 py-3">
                    {getTaskCategoryName(sub.task_category_id)}
                  </td>
                  <td className="px-4 py-3">{sub.case_count}</td>
                  <td className="px-4 py-3">{getStatusBadge(sub.status)}</td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => handleViewDetail(sub)}
                      className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium hover:bg-accent"
                    >
                      <Eye className="h-3 w-3" />
                      View
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
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
                  <span className="font-medium">{selectedSubmission.case_count}</span>
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

              {/* Review info (if reviewed) */}
              {(selectedSubmission.reviewed_by || selectedSubmission.review_notes) && (
                <div className="rounded-md bg-muted/50 p-3">
                  <p className="text-sm font-medium">Review Information</p>
                  <p className="text-xs text-muted-foreground">
                    Reviewed by: {selectedSubmission.reviewed_by || "Unknown"}
                  </p>
                  {selectedSubmission.review_notes && (
                    <p className="mt-1 text-sm">{selectedSubmission.review_notes}</p>
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

              {/* Review Actions - Supervisor only */}
              {!isStudent && selectedSubmission.status === "pending" && (
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
    </div>
  );
}
