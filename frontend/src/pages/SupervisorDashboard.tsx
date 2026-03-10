// frontend/src/pages/SupervisorDashboard.tsx

import { useCallback, useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { dashboardService } from "@/services/dashboard";
import type {
  SupervisorDashboardData,
  StudentSummary,
  StudentDashboardData,
  DepartmentProgress,
} from "@/types/dashboard";
import StudentDistribution from "@/components/charts/StudentDistribution";
import ProgressGauge from "@/components/charts/ProgressGauge";
import DepartmentBars from "@/components/charts/DepartmentBars";
import ProgressTimeline from "@/components/charts/ProgressTimeline";
import {
  AlertCircle, Users, CheckCircle, AlertTriangle, XCircle,
  Eye, X, ChevronDown, ChevronRight, Search,
} from "lucide-react";
import { DashboardSkeleton } from "@/components/skeletons/DashboardSkeleton";

const STATUS_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  on_track: { bg: "bg-green-100", text: "text-green-700", label: "On Track" },
  at_risk: { bg: "bg-yellow-100", text: "text-yellow-700", label: "At Risk" },
  behind: { bg: "bg-red-100", text: "text-red-700", label: "Behind" },
};

export default function SupervisorDashboard() {
  const [data, setData] = useState<SupervisorDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [selectedStudent, setSelectedStudent] = useState<StudentDashboardData | null>(null);
  const [studentLoading, setStudentLoading] = useState(false);
  const [expandedDept, setExpandedDept] = useState<string | null>(null);

  const loadDashboard = useCallback(async () => {
    try {
      setLoading(true);
      setError("");
      const result = await dashboardService.getSupervisorDashboard();
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

  const viewStudent = async (studentId: string) => {
    try {
      setStudentLoading(true);
      const result = await dashboardService.getStudentDashboardById(studentId);
      setSelectedStudent(result);
    } catch {
      setError("Failed to load student data");
    } finally {
      setStudentLoading(false);
    }
  };

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

  // Filter students
  const filteredStudents = data.students.filter((s: StudentSummary) => {
    const matchesSearch =
      s.student_name.toLowerCase().includes(search.toLowerCase()) ||
      s.student_email.toLowerCase().includes(search.toLowerCase()) ||
      (s.student_code && s.student_code.toLowerCase().includes(search.toLowerCase()));
    const matchesStatus = statusFilter === "all" || s.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Supervisor Dashboard</h1>

      {/* Summary cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardContent className="flex items-center gap-3 pt-6">
            <Users className="h-8 w-8 text-muted-foreground" />
            <div>
              <div className="text-2xl font-bold">{data.total_students}</div>
              <p className="text-sm text-muted-foreground">Total Students</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 pt-6">
            <CheckCircle className="h-8 w-8 text-green-500" />
            <div>
              <div className="text-2xl font-bold">{data.on_track_count}</div>
              <p className="text-sm text-muted-foreground">On Track</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 pt-6">
            <AlertTriangle className="h-8 w-8 text-yellow-500" />
            <div>
              <div className="text-2xl font-bold">{data.at_risk_count}</div>
              <p className="text-sm text-muted-foreground">At Risk</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 pt-6">
            <XCircle className="h-8 w-8 text-red-500" />
            <div>
              <div className="text-2xl font-bold">{data.behind_count}</div>
              <p className="text-sm text-muted-foreground">Behind</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Distribution chart */}
      <Card>
        <CardHeader>
          <CardTitle>Student Status Distribution</CardTitle>
        </CardHeader>
        <CardContent>
          <StudentDistribution
            onTrack={data.on_track_count}
            atRisk={data.at_risk_count}
            behind={data.behind_count}
          />
        </CardContent>
      </Card>

      {/* Student table */}
      <Card>
        <CardHeader>
          <CardTitle>Students</CardTitle>
          <div className="flex gap-3 mt-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search by name, email, or ID..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9"
              />
            </div>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="rounded-md border bg-background px-3 py-2 text-sm"
            >
              <option value="all">All Statuses</option>
              <option value="on_track">On Track</option>
              <option value="at_risk">At Risk</option>
              <option value="behind">Behind</option>
            </select>
          </div>
        </CardHeader>
        <CardContent>
          {filteredStudents.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4 text-center">
              No students found
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="pb-2 font-medium">Student</th>
                    <th className="pb-2 font-medium">Department</th>
                    <th className="pb-2 font-medium text-right">Progress</th>
                    <th className="pb-2 font-medium text-right">Status</th>
                    <th className="pb-2 font-medium text-right">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredStudents.map((student: StudentSummary) => {
                    const style = STATUS_STYLES[student.status] || STATUS_STYLES.behind;
                    return (
                      <tr key={student.student_id} className="border-b last:border-0">
                        <td className="py-3">
                          <div className="font-medium">
                            {student.student_name || "Unknown"}
                            {student.student_code && (
                              <span className="text-muted-foreground font-normal">
                                {" "}({student.student_code})
                              </span>
                            )}
                          </div>
                          <div className="text-xs text-muted-foreground">{student.student_email}</div>
                        </td>
                        <td className="py-3">{student.current_department || "—"}</td>
                        <td className="py-3">{student.current_department || "—"}</td>
                        <td className="py-3 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <div className="w-20 rounded-full bg-secondary h-2">
                              <div
                                className="h-2 rounded-full bg-primary transition-all"
                                style={{ width: `${Math.min(student.overall_completion_percentage, 100)}%` }}
                              />
                            </div>
                            <span className="w-12 text-right">
                              {student.overall_completion_percentage.toFixed(1)}%
                            </span>
                          </div>
                        </td>
                        <td className="py-3 text-right">
                          <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${style.bg} ${style.text}`}>
                            {style.label}
                          </span>
                        </td>
                        <td className="py-3 text-right">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => viewStudent(student.student_id)}
                            disabled={studentLoading}
                          >
                            <Eye className="h-4 w-4" />
                          </Button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Student detail modal */}
      {selectedStudent && (
        <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/50 p-4 pt-10">
          <div className="w-full max-w-4xl rounded-lg bg-background border shadow-lg">
            <div className="flex items-center justify-between border-b px-6 py-4">
              <h2 className="text-lg font-semibold">{selectedStudent.student_name}</h2>
              <Button variant="ghost" size="sm" onClick={() => { setSelectedStudent(null); setExpandedDept(null); }}>
                <X className="h-4 w-4" />
              </Button>
            </div>
            <div className="p-6 space-y-6 max-h-[70vh] overflow-y-auto">
              {/* Student detail: gauge + summary */}
              <div className="grid gap-4 md:grid-cols-3">
                <div className="flex items-center justify-center">
                  <ProgressGauge percentage={selectedStudent.overall_completion_percentage} size={150} />
                </div>
                <Card>
                  <CardContent className="pt-6">
                    <div className="text-2xl font-bold">{selectedStudent.total_completed}</div>
                    <p className="text-sm text-muted-foreground">of {selectedStudent.total_required} required</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-6">
                    <div className="text-2xl font-bold">{selectedStudent.current_department || "None"}</div>
                    <p className="text-sm text-muted-foreground">Current Rotation</p>
                  </CardContent>
                </Card>
              </div>

              {/* Charts */}
              <div className="grid gap-4 lg:grid-cols-2">
                <Card>
                  <CardHeader><CardTitle className="text-base">Department Progress</CardTitle></CardHeader>
                  <CardContent>
                    <DepartmentBars departments={selectedStudent.departments} />
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader><CardTitle className="text-base">Progress Over Time</CardTitle></CardHeader>
                  <CardContent>
                    <ProgressTimeline data={selectedStudent.progress_over_time} />
                  </CardContent>
                </Card>
              </div>

              {/* Category breakdown */}
              <Card>
                <CardHeader><CardTitle className="text-base">Category Breakdown</CardTitle></CardHeader>
                <CardContent className="space-y-2">
                  {selectedStudent.departments.map((dept: DepartmentProgress) => (
                    <div key={dept.department_id} className="rounded border">
                      <button
                        onClick={() => setExpandedDept(prev => prev === dept.department_id ? null : dept.department_id)}
                        className="flex w-full items-center justify-between px-3 py-2 text-left hover:bg-accent/50 text-sm"
                      >
                        <div className="flex items-center gap-2">
                          {expandedDept === dept.department_id
                            ? <ChevronDown className="h-3 w-3" />
                            : <ChevronRight className="h-3 w-3" />
                          }
                          <span className="font-medium">{dept.department_name}</span>
                        </div>
                        <span className="text-muted-foreground">
                          {dept.total_completed}/{dept.total_required} ({dept.completion_percentage.toFixed(1)}%)
                        </span>
                      </button>
                      {expandedDept === dept.department_id && (
                        <div className="border-t px-3 py-2 space-y-2">
                          {dept.categories.map(cat => (
                            <div key={cat.category_id} className="flex items-center justify-between text-sm">
                              <span>{cat.category_name}</span>
                              <span className="text-muted-foreground">
                                {cat.completed_count}/{cat.required_count}
                                {cat.pending_count > 0 && <span className="text-yellow-600 ml-1">(+{cat.pending_count} pending)</span>}
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </CardContent>
              </Card>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
