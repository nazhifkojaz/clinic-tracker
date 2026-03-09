import type {
  Department,
  DepartmentCreate,
  DepartmentUpdate,
  DepartmentWithCategories,
  TaskCategory,
  TaskCategoryCreate,
  TaskCategoryUpdate,
} from "@/types/department";
import api from "./api";

export const departmentService = {
  async list(): Promise<Department[]> {
    const { data } = await api.get<Department[]>("/api/departments");
    return data;
  },

  async get(id: string): Promise<DepartmentWithCategories> {
    const { data } = await api.get<DepartmentWithCategories>(
      `/api/departments/${id}`
    );
    return data;
  },

  async create(body: DepartmentCreate): Promise<Department> {
    const { data } = await api.post<Department>("/api/departments", body);
    return data;
  },

  async update(id: string, body: DepartmentUpdate): Promise<Department> {
    const { data } = await api.patch<Department>(
      `/api/departments/${id}`,
      body
    );
    return data;
  },

  // --- Task Categories ---

  async listCategories(departmentId: string): Promise<TaskCategory[]> {
    const { data } = await api.get<TaskCategory[]>(
      `/api/departments/${departmentId}/categories`
    );
    return data;
  },

  async createCategory(
    departmentId: string,
    body: TaskCategoryCreate
  ): Promise<TaskCategory> {
    const { data } = await api.post<TaskCategory>(
      `/api/departments/${departmentId}/categories`,
      body
    );
    return data;
  },

  async updateCategory(
    departmentId: string,
    categoryId: string,
    body: TaskCategoryUpdate
  ): Promise<TaskCategory> {
    const { data } = await api.patch<TaskCategory>(
      `/api/departments/${departmentId}/categories/${categoryId}`,
      body
    );
    return data;
  },
};
