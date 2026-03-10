import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { userService } from "@/services/users";
import type { User, UserCreate, UserRole } from "@/types/user";
import { Loader2, Plus, Pencil } from "lucide-react";

export default function UserManagement() {
  const [users, setUsers] = useState<User[]>([]);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [formData, setFormData] = useState({
    email: "",
    password: "",
    full_name: "",
    student_id: "",
    role: "student" as UserRole,
  });
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const fetchUsers = async () => {
    const data = await userService.list();
    setUsers(data);
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  const openCreateModal = () => {
    setEditingUser(null);
    setFormData({ email: "", password: "", full_name: "", student_id: "", role: "student" });
    setError("");
    setIsModalOpen(true);
  };

  const openEditModal = (user: User) => {
    setEditingUser(user);
    setFormData({
      email: user.email,
      password: "",
      full_name: user.full_name,
      student_id: user.student_id || "",
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
          student_id: formData.student_id || null,
          role: formData.role,
        };
        if (formData.password) updateData.password = formData.password;
        await userService.update(editingUser.id, updateData);
      } else {
        await userService.create(formData as UserCreate);
      }
      setIsModalOpen(false);
      fetchUsers();
    } catch {
      setError(editingUser ? "Failed to update user." : "Failed to create user. Email may already exist.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const roleBadgeColor: Record<UserRole, string> = {
    admin: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
    supervisor: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
    student: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">User Management</h1>
        <Button onClick={openCreateModal}>
          <Plus className="mr-2 h-4 w-4" />
          Create User
        </Button>
      </div>

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
                    <span className={`rounded-full px-2 py-1 text-xs font-medium capitalize ${roleBadgeColor[user.role]}`}>
                      {user.role}
                    </span>
                  </td>
                  <td className="p-4">
                    <span className={`text-sm ${user.is_active ? "text-green-600" : "text-red-500"}`}>
                      {user.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="p-4">
                    <Button variant="ghost" size="icon-sm" onClick={() => openEditModal(user)}>
                      <Pencil className="h-4 w-4" />
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        </CardContent>
      </Card>

      {/* Modal Overlay */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <Card className="w-full max-w-md">
            <CardHeader>
              <CardTitle>{editingUser ? "Edit User" : "Create User"}</CardTitle>
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
                    onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="modal_email">Email</Label>
                  <Input
                    id="modal_email"
                    type="email"
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="modal_password">
                    Password {editingUser && "(leave blank to keep current)"}
                  </Label>
                  <Input
                    id="modal_password"
                    type="password"
                    value={formData.password}
                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                    required={!editingUser}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="role">Role</Label>
                  <select
                    id="role"
                    className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm"
                    value={formData.role}
                    onChange={(e) => setFormData({ ...formData, role: e.target.value as UserRole })}
                  >
                    <option value="student">Student</option>
                    <option value="supervisor">Supervisor</option>
                    <option value="admin">Admin</option>
                  </select>
                </div>
                {formData.role === "student" && (
                  <div className="space-y-2">
                    <Label htmlFor="student_id">Student ID</Label>
                    <Input
                      id="student_id"
                      value={formData.student_id}
                      onChange={(e) => setFormData({ ...formData, student_id: e.target.value })}
                    />
                  </div>
                )}
                <div className="flex justify-end gap-2">
                  <Button type="button" variant="outline" onClick={() => setIsModalOpen(false)}>
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
    </div>
  );
}
