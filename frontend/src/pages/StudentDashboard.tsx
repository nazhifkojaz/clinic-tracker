// frontend/src/pages/StudentDashboard.tsx

import { useCallback, useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { dashboardService } from "@/services/dashboard";
import type { StudentDashboardData, DepartmentProgress } from "@/types/dashboard";
import ProgressGauge from "@/components/charts/ProgressGauge";
import ProgressTimeline from "@/components/charts/ProgressTimeline";
import DepartmentBars from "@/components/charts/DepartmentBars";
import { AlertCircle, ChevronDown, ChevronRight } from "lucide-react";
import { DashboardSkeleton } from "@/components/skeletons/DashboardSkeleton";

export default function StudentDashboard() {
  const [data, setData] = useState<StudentDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [expandedDept, setExpandedDept] = useState<string | null>(null);

  const loadDashboard = useCallback(async () => {
    try {
      setLoading(true);
      setError("");
      const result = await dashboardService.getStudentDashboard();
      setData(result);
    } catch {
      setError("Failed to load dashboard data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  if (loading) {
    return <DashboardSkeleton />;
  }

  if (error || !data) {
    return (
      <div className="flex items-center justify-center gap-2 py-20 text-destructive">
        <AlertCircle className="h-5 w-5" />
        <span>{error || "No data available"}</span>
      </div>
    );
  }

  const toggleDept = (deptId: string) => {
    setExpandedDept((prev) => (prev === deptId ? null : deptId));
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">My Dashboard</h1>

      {/* Current rotation banner */}
      {data.current_department && (
        <div className="rounded-lg border bg-primary/5 px-4 py-3">
          <span className="text-sm text-muted-foreground">Current Rotation:</span>{" "}
          <span className="font-semibold">{data.current_department}</span>
        </div>
      )}

      {/* Top row: Gauge + Summary cards */}
      <div className="grid gap-6 md:grid-cols-3">
        <Card className="flex items-center justify-center py-4">
          <ProgressGauge percentage={data.overall_completion_percentage} />
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Completed
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{data.total_completed}</div>
            <p className="text-sm text-muted-foreground">
              of {data.total_required} required
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Departments
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{data.departments.length}</div>
            <p className="text-sm text-muted-foreground">
              {data.departments.filter((d) => d.completion_percentage >= 100).length} completed
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Charts row */}
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Department Progress</CardTitle>
          </CardHeader>
          <CardContent>
            <DepartmentBars departments={data.departments} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Progress Over Time</CardTitle>
          </CardHeader>
          <CardContent>
            <ProgressTimeline data={data.progress_over_time} />
          </CardContent>
        </Card>
      </div>

      {/* Department breakdown (expandable) */}
      <Card>
        <CardHeader>
          <CardTitle>Department Details</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {data.departments.map((dept: DepartmentProgress) => (
            <div key={dept.department_id} className="rounded-lg border">
              <button
                onClick={() => toggleDept(dept.department_id)}
                className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-accent/50 transition-colors"
              >
                <div className="flex items-center gap-3">
                  {expandedDept === dept.department_id ? (
                    <ChevronDown className="h-4 w-4" />
                  ) : (
                    <ChevronRight className="h-4 w-4" />
                  )}
                  <span className="font-medium">{dept.department_name}</span>
                </div>
                <div className="flex items-center gap-4">
                  <span className="text-sm text-muted-foreground">
                    {dept.total_completed}/{dept.total_required}
                  </span>
                  <div className="w-24 rounded-full bg-secondary h-2">
                    <div
                      className="h-2 rounded-full bg-primary transition-all"
                      style={{ width: `${Math.min(dept.completion_percentage, 100)}%` }}
                    />
                  </div>
                  <span className="text-sm font-medium w-14 text-right">
                    {dept.completion_percentage.toFixed(1)}%
                  </span>
                </div>
              </button>

              {expandedDept === dept.department_id && (
                <div className="border-t px-4 py-3 space-y-3">
                  {dept.categories.map((cat) => (
                    <div key={cat.category_id} className="flex items-center justify-between">
                      <span className="text-sm">{cat.category_name}</span>
                      <div className="flex items-center gap-4">
                        <span className="text-sm text-muted-foreground">
                          {cat.completed_count}/{cat.required_count}
                          {cat.pending_count > 0 && (
                            <span className="text-yellow-600 ml-1">
                              (+{cat.pending_count} pending)
                            </span>
                          )}
                        </span>
                        <div className="w-20 rounded-full bg-secondary h-1.5">
                          <div
                            className="h-1.5 rounded-full bg-primary transition-all"
                            style={{ width: `${Math.min(cat.completion_percentage, 100)}%` }}
                          />
                        </div>
                        <span className="text-xs font-medium w-12 text-right">
                          {cat.completion_percentage.toFixed(0)}%
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </CardContent>
      </Card>

      {/* Recent submissions */}
      <Card>
        <CardHeader>
          <CardTitle>Recent Submissions</CardTitle>
        </CardHeader>
        <CardContent>
          {data.recent_submissions.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4 text-center">
              No submissions yet
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="pb-2 font-medium">Date</th>
                    <th className="pb-2 font-medium">Department</th>
                    <th className="pb-2 font-medium">Category</th>
                    <th className="pb-2 font-medium text-right">Cases</th>
                    <th className="pb-2 font-medium text-right">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {data.recent_submissions.map((sub) => (
                    <tr key={sub.id} className="border-b last:border-0">
                      <td className="py-2">{new Date(sub.created_at).toLocaleDateString()}</td>
                      <td className="py-2">{sub.department_name}</td>
                      <td className="py-2">{sub.category_name}</td>
                      <td className="py-2 text-right">{sub.case_count}</td>
                      <td className="py-2 text-right">
                        <span
                          className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
                            sub.status === "approved"
                              ? "bg-green-100 text-green-700"
                              : sub.status === "rejected"
                              ? "bg-red-100 text-red-700"
                              : "bg-yellow-100 text-yellow-700"
                          }`}
                        >
                          {sub.status}
                        </span>
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
