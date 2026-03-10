import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { departmentService } from "@/services/departments";
import type {
  Department,
  DepartmentCreate,
  TaskCategory,
  TaskCategoryCreate,
} from "@/types/department";
import {
  Loader2,
  Plus,
  Pencil,
  ChevronDown,
  ChevronRight,
  Trash2,
  AlertCircle,
} from "lucide-react";

type CategoryFormData = Omit<TaskCategoryCreate, "description"> & {
  description?: string;
};

export default function DepartmentManagement() {
  const [departments, setDepartments] = useState<Department[]>([]);
  const [expandedDeptId, setExpandedDeptId] = useState<string | null>(null);
  const [expandedDeptCategories, setExpandedDeptCategories] = useState<
    TaskCategory[]
  >([]);
  const [isDeptModalOpen, setIsDeptModalOpen] = useState(false);
  const [isCategoryModalOpen, setIsCategoryModalOpen] = useState(false);
  const [editingDepartment, setEditingDepartment] = useState<Department | null>(
    null
  );
  const [editingCategory, setEditingCategory] =
    useState<TaskCategory | null>(null);
  const [deptFormData, setDeptFormData] = useState<DepartmentCreate>({
    name: "",
    description: "",
  });
  const [categoryFormData, setCategoryFormData] = useState<CategoryFormData>({
    name: "",
    required_count: 1,
    description: "",
  });
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  const fetchDepartments = async () => {
    setIsLoading(true);
    try {
      const data = await departmentService.list();
      setDepartments(data);
    } catch {
      setError("Failed to load departments.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchDepartments();
  }, []);

  const openCreateDeptModal = () => {
    setEditingDepartment(null);
    setDeptFormData({ name: "", description: "" });
    setError("");
    setIsDeptModalOpen(true);
  };

  const openEditDeptModal = (dept: Department) => {
    setEditingDepartment(dept);
    setDeptFormData({
      name: dept.name,
      description: dept.description || "",
    });
    setError("");
    setIsDeptModalOpen(true);
  };

  const openCreateCategoryModal = () => {
    setEditingCategory(null);
    setCategoryFormData({ name: "", required_count: 1, description: "" });
    setError("");
    setIsCategoryModalOpen(true);
  };

  const openEditCategoryModal = (category: TaskCategory) => {
    setEditingCategory(category);
    setCategoryFormData({
      name: category.name,
      required_count: category.required_count,
      description: category.description || "",
    });
    setError("");
    setIsCategoryModalOpen(true);
  };

  const handleDeptSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError("");

    try {
      if (editingDepartment) {
        await departmentService.update(editingDepartment.id, deptFormData);
      } else {
        await departmentService.create(deptFormData);
      }
      setIsDeptModalOpen(false);
      fetchDepartments();
    } catch {
      setError(
        editingDepartment
          ? "Failed to update department."
          : "Failed to create department. Name may already exist."
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCategorySubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!expandedDeptId) return;

    setIsSubmitting(true);
    setError("");

    try {
      if (editingCategory) {
        await departmentService.updateCategory(
          expandedDeptId,
          editingCategory.id,
          categoryFormData
        );
      } else {
        await departmentService.createCategory(
          expandedDeptId,
          categoryFormData
        );
      }
      setIsCategoryModalOpen(false);
      await fetchDepartmentCategories(expandedDeptId);
    } catch {
      setError("Failed to save task category.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeactivateDept = async (dept: Department) => {
    if (
      !confirm(
        `Are you sure you want to deactivate "${dept.name}"? This will make all its task categories inaccessible.`
      )
    ) {
      return;
    }

    try {
      await departmentService.update(dept.id, { is_active: false });
      fetchDepartments();
      if (expandedDeptId === dept.id) {
        setExpandedDeptId(null);
      }
    } catch {
      setError("Failed to deactivate department.");
    }
  };

  const handleDeactivateCategory = async (category: TaskCategory) => {
    if (
      !confirm(
        `Are you sure you want to deactivate "${category.name}"?`
      )
    ) {
      return;
    }

    try {
      await departmentService.updateCategory(
        expandedDeptId!,
        category.id,
        { is_active: false }
      );
      await fetchDepartmentCategories(expandedDeptId!);
    } catch {
      setError("Failed to deactivate task category.");
    }
  };

  const fetchDepartmentCategories = async (deptId: string) => {
    try {
      const dept = await departmentService.get(deptId);
      setExpandedDeptCategories(dept.task_categories);
    } catch {
      setError("Failed to load task categories.");
    }
  };

  const toggleExpand = async (deptId: string) => {
    if (expandedDeptId === deptId) {
      setExpandedDeptId(null);
      setExpandedDeptCategories([]);
    } else {
      setExpandedDeptId(deptId);
      await fetchDepartmentCategories(deptId);
    }
  };

  const getCategoryCount = (deptId: string) => {
    if (expandedDeptId === deptId) {
      return expandedDeptCategories.length;
    }
    // For collapsed departments, we don't have the category count
    // Return a placeholder or fetch separately if needed
    return 0;
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Department Management</h1>
        <Button onClick={openCreateDeptModal}>
          <Plus className="mr-2 h-4 w-4" />
          Create Department
        </Button>
      </div>

      {error && (
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
                  <th className="p-4 w-10"></th>
                  <th className="p-4">Name</th>
                  <th className="p-4">Description</th>
                  <th className="p-4">Categories</th>
                  <th className="p-4">Status</th>
                  <th className="p-4">Actions</th>
                </tr>
              </thead>
              <tbody>
                {departments.map((dept) => (
                  <>
                    <tr key={dept.id} className="border-b last:border-0">
                      <td className="p-4">
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          onClick={() => toggleExpand(dept.id)}
                        >
                          {expandedDeptId === dept.id ? (
                            <ChevronDown className="h-4 w-4" />
                          ) : (
                            <ChevronRight className="h-4 w-4" />
                          )}
                        </Button>
                      </td>
                      <td className="p-4 font-medium">{dept.name}</td>
                      <td className="p-4 text-muted-foreground">
                        {dept.description || "-"}
                      </td>
                      <td className="p-4">
                        <span className="text-sm">
                          {getCategoryCount(dept.id)}
                        </span>
                      </td>
                      <td className="p-4">
                        <span
                          className={`text-sm ${
                            dept.is_active
                              ? "text-green-600"
                              : "text-red-500"
                          }`}
                        >
                          {dept.is_active ? "Active" : "Inactive"}
                        </span>
                      </td>
                      <td className="p-4">
                        <div className="flex gap-1">
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            onClick={() => openEditDeptModal(dept)}
                          >
                            <Pencil className="h-4 w-4" />
                          </Button>
                          {dept.is_active && (
                            <Button
                              variant="ghost"
                              size="icon-sm"
                              onClick={() => handleDeactivateDept(dept)}
                            >
                              <Trash2 className="h-4 w-4 text-destructive" />
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                    {expandedDeptId === dept.id && (
                      <tr>
                        <td colSpan={6} className="p-4 bg-muted/30">
                          <div className="space-y-3">
                            <div className="flex items-center justify-between">
                              <h3 className="text-sm font-semibold">
                                Task Categories
                              </h3>
                              <Button
                                size="sm"
                                onClick={openCreateCategoryModal}
                              >
                                <Plus className="mr-1 h-3 w-3" />
                                Add Category
                              </Button>
                            </div>
                            {expandedDeptCategories.length === 0 ? (
                              <div className="flex items-center gap-2 text-sm text-muted-foreground py-4">
                                <AlertCircle className="h-4 w-4" />
                                <span>No task categories yet</span>
                              </div>
                            ) : (
                              <div className="border rounded-md overflow-hidden">
                                <table className="w-full text-sm">
                                  <thead className="bg-muted/50">
                                    <tr className="text-left text-muted-foreground">
                                      <th className="p-3">Name</th>
                                      <th className="p-3">Required Count</th>
                                      <th className="p-3">Description</th>
                                      <th className="p-3">Status</th>
                                      <th className="p-3">Actions</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {expandedDeptCategories.map((cat) => (
                                      <tr
                                        key={cat.id}
                                        className="border-t last:border-0"
                                      >
                                        <td className="p-3 font-medium">
                                          {cat.name}
                                        </td>
                                        <td className="p-3">
                                          {cat.required_count}
                                        </td>
                                        <td className="p-3 text-muted-foreground">
                                          {cat.description || "-"}
                                        </td>
                                        <td className="p-3">
                                          <span
                                            className={`text-xs ${
                                              cat.is_active
                                                ? "text-green-600"
                                                : "text-red-500"
                                            }`}
                                          >
                                            {cat.is_active
                                              ? "Active"
                                              : "Inactive"}
                                          </span>
                                        </td>
                                        <td className="p-3">
                                          <div className="flex gap-1">
                                            <Button
                                              variant="ghost"
                                              size="icon-sm"
                                              onClick={() =>
                                                openEditCategoryModal(cat)
                                              }
                                            >
                                              <Pencil className="h-3 w-3" />
                                            </Button>
                                            {cat.is_active && (
                                              <Button
                                                variant="ghost"
                                                size="icon-sm"
                                                onClick={() =>
                                                  handleDeactivateCategory(
                                                    cat
                                                  )
                                                }
                                              >
                                                <Trash2 className="h-3 w-3 text-destructive" />
                                              </Button>
                                            )}
                                          </div>
                                        </td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      {/* Department Modal */}
      {isDeptModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <Card className="w-full max-w-md">
            <CardHeader>
              <CardTitle>
                {editingDepartment ? "Edit Department" : "Create Department"}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleDeptSubmit} className="space-y-4">
                {error && (
                  <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                    {error}
                  </div>
                )}
                <div className="space-y-2">
                  <Label htmlFor="dept_name">Name</Label>
                  <Input
                    id="dept_name"
                    value={deptFormData.name}
                    onChange={(e) =>
                      setDeptFormData({
                        ...deptFormData,
                        name: e.target.value,
                      })
                    }
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="dept_description">Description</Label>
                  <Input
                    id="dept_description"
                    value={deptFormData.description ?? ""}
                    onChange={(e) =>
                      setDeptFormData({
                        ...deptFormData,
                        description: e.target.value,
                      })
                    }
                  />
                </div>
                <div className="flex justify-end gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setIsDeptModalOpen(false)}
                  >
                    Cancel
                  </Button>
                  <Button type="submit" disabled={isSubmitting}>
                    {isSubmitting ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Saving...
                      </>
                    ) : editingDepartment ? (
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

      {/* Task Category Modal */}
      {isCategoryModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <Card className="w-full max-w-md">
            <CardHeader>
              <CardTitle>
                {editingCategory
                  ? "Edit Task Category"
                  : "Create Task Category"}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleCategorySubmit} className="space-y-4">
                {error && (
                  <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                    {error}
                  </div>
                )}
                <div className="space-y-2">
                  <Label htmlFor="cat_name">Name</Label>
                  <Input
                    id="cat_name"
                    value={categoryFormData.name}
                    onChange={(e) =>
                      setCategoryFormData({
                        ...categoryFormData,
                        name: e.target.value,
                      })
                    }
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="required_count">Required Count</Label>
                  <Input
                    id="required_count"
                    type="number"
                    min="1"
                    value={categoryFormData.required_count}
                    onChange={(e) =>
                      setCategoryFormData({
                        ...categoryFormData,
                        required_count: parseInt(e.target.value) || 1,
                      })
                    }
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="cat_description">Description</Label>
                  <Input
                    id="cat_description"
                    value={categoryFormData.description}
                    onChange={(e) =>
                      setCategoryFormData({
                        ...categoryFormData,
                        description: e.target.value,
                      })
                    }
                  />
                </div>
                <div className="flex justify-end gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setIsCategoryModalOpen(false)}
                  >
                    Cancel
                  </Button>
                  <Button type="submit" disabled={isSubmitting}>
                    {isSubmitting ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Saving...
                      </>
                    ) : editingCategory ? (
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
