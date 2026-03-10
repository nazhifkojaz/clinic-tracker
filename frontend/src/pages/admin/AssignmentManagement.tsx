import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { assignmentService } from "@/services/assignments";
import { userService } from "@/services/users";
import { departmentService } from "@/services/departments";
import type { AssignmentWithDetails, AssignmentType } from "@/types/assignment";
import type { User } from "@/types/user";
import type { Department } from "@/types/department";
import { Plus, Trash2 } from "lucide-react";

export default function AssignmentManagement() {
  const [assignments, setAssignments] = useState<AssignmentWithDetails[]>([]);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [users, setUsers] = useState<User[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [formData, setFormData] = useState({
    supervisor_id: "",
    student_id: "",
    assignment_type: "primary" as AssignmentType,
    department_id: "",
  });
  const [assignmentTypeError, setAssignmentTypeError] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  const supervisors = users.filter(
    (u) => (u.role === "supervisor" || u.role === "admin") && u.is_active
  );
  const students = users.filter((u) => u.role === "student" && u.is_active);

  const fetchAssignments = async () => {
    setIsLoading(true);
    try {
      const data = await assignmentService.list();
      setAssignments(data);
    } catch {
      setError("Failed to load assignments.");
    } finally {
      setIsLoading(false);
    }
  };

  const fetchFormData = async () => {
    try {
      const [usersData, deptsData] = await Promise.all([
        userService.list(),
        departmentService.list(),
      ]);
      setUsers(usersData);
      setDepartments(deptsData);
    } catch {
      setError("Failed to load form data.");
    }
  };

  useEffect(() => {
    fetchAssignments();
  }, []);

  const openCreateModal = () => {
    setFormData({
      supervisor_id: "",
      student_id: "",
      assignment_type: "primary",
      department_id: "",
    });
    setError("");
    setAssignmentTypeError("");
    setIsModalOpen(true);
    fetchFormData();
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm("Remove this assignment?")) return;
    try {
      await assignmentService.remove(id);
      fetchAssignments();
    } catch {
      alert("Failed to remove assignment.");
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError("");
    setAssignmentTypeError("");

    // Validation based on assignment type
    if (formData.assignment_type === "primary" && !formData.student_id) {
      setAssignmentTypeError("Please select a student for primary assignments.");
      setIsSubmitting(false);
      return;
    }
    if (formData.assignment_type === "department" && !formData.department_id) {
      setAssignmentTypeError("Please select a department for department assignments.");
      setIsSubmitting(false);
      return;
    }

    try {
      await assignmentService.create({
        supervisor_id: formData.supervisor_id,
        student_id: formData.assignment_type === "primary" ? formData.student_id : null,
        assignment_type: formData.assignment_type,
        department_id: formData.assignment_type === "department" ? formData.department_id : null,
      });
      setIsModalOpen(false);
      fetchAssignments();
    } catch {
      setError("Failed to create assignment. It may already exist.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const typeBadgeColor: Record<AssignmentType, string> = {
    primary:
      "bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300",
    department:
      "bg-teal-100 text-teal-700 dark:bg-teal-900 dark:text-teal-300",
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Supervisor Assignments</h1>
        <Button onClick={openCreateModal}>
          <Plus className="mr-2 h-4 w-4" />
          Create Assignment
        </Button>
      </div>

      {error && !isModalOpen && (
        <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {isLoading ? (
        <div className="flex items-center justify-center py-8">
          <div className="text-muted-foreground">Loading...</div>
        </div>
      ) : (
        <Card>
          <CardContent className="p-0">
            <table className="w-full">
              <thead>
                <tr className="border-b text-left text-sm text-muted-foreground">
                  <th className="p-4">Supervisor</th>
                  <th className="p-4">Student</th>
                  <th className="p-4">Type</th>
                  <th className="p-4">Department</th>
                  <th className="p-4">Actions</th>
                </tr>
              </thead>
              <tbody>
                {assignments.length === 0 ? (
                  <tr>
                    <td
                      colSpan={5}
                      className="p-8 text-center text-muted-foreground"
                    >
                      No assignments yet. Create one to get started.
                    </td>
                  </tr>
                ) : (
                  assignments.map((a) => (
                    <tr key={a.id} className="border-b last:border-0">
                      <td className="p-4 font-medium">{a.supervisor_name}</td>
                      <td className="p-4">
                        {a.assignment_type === "department"
                          ? `All students in ${a.department_name || "the department"}`
                          : a.student_name || "—"}
                      </td>
                      <td className="p-4">
                        <span
                          className={`rounded-full px-2 py-1 text-xs font-medium capitalize ${typeBadgeColor[a.assignment_type]}`}
                        >
                          {a.assignment_type}
                        </span>
                      </td>
                      <td className="p-4 text-muted-foreground">
                        {a.department_name || "—"}
                      </td>
                      <td className="p-4">
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          onClick={() => handleDelete(a.id)}
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      {/* Create Assignment Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <Card className="w-full max-w-md">
            <CardHeader>
              <CardTitle>Create Assignment</CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-4">
                {(error || assignmentTypeError) && (
                  <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                    {error || assignmentTypeError}
                  </div>
                )}
                <div className="space-y-2">
                  <Label htmlFor="supervisor">Supervisor</Label>
                  <select
                    id="supervisor"
                    className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm"
                    value={formData.supervisor_id}
                    onChange={(e) =>
                      setFormData({ ...formData, supervisor_id: e.target.value })
                    }
                    required
                  >
                    <option value="">Select supervisor...</option>
                    {supervisors.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.full_name} ({s.email})
                      </option>
                    ))}
                  </select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="assignment_type">Assignment Type</Label>
                  <select
                    id="assignment_type"
                    className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm"
                    value={formData.assignment_type}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        assignment_type: e.target.value as AssignmentType,
                        student_id: e.target.value === "department" ? "" : formData.student_id,
                        department_id: e.target.value === "primary" ? "" : formData.department_id,
                      })
                    }
                  >
                    <option value="primary">
                      Primary — overall student supervisor
                    </option>
                    <option value="department">
                      Department — supervise all students in a department
                    </option>
                  </select>
                </div>
                {formData.assignment_type === "primary" && (
                  <div className="space-y-2">
                    <Label htmlFor="student">Student</Label>
                    <select
                      id="student"
                      className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm"
                      value={formData.student_id}
                      onChange={(e) =>
                        setFormData({ ...formData, student_id: e.target.value })
                      }
                      required
                    >
                      <option value="">Select student...</option>
                      {students.map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.full_name}
                          {s.student_id ? ` (${s.student_id})` : ""} — {s.email}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
                {formData.assignment_type === "department" && (
                  <div className="space-y-2">
                    <Label htmlFor="department">Department</Label>
                    <select
                      id="department"
                      className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm"
                      value={formData.department_id}
                      onChange={(e) =>
                        setFormData({
                          ...formData,
                          department_id: e.target.value,
                        })
                      }
                      required
                    >
                      <option value="">Select department...</option>
                      {departments.map((d) => (
                        <option key={d.id} value={d.id}>
                          {d.name}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
                <div className="flex justify-end gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setIsModalOpen(false)}
                  >
                    Cancel
                  </Button>
                  <Button type="submit" disabled={isSubmitting}>
                    {isSubmitting ? "Creating..." : "Create"}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
