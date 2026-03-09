export interface Department {
  id: string;
  name: string;
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface DepartmentWithCategories extends Department {
  task_categories: TaskCategory[];
}

export interface DepartmentCreate {
  name: string;
  description?: string | null;
}

export interface DepartmentUpdate {
  name?: string;
  description?: string | null;
  is_active?: boolean;
}

export interface TaskCategory {
  id: string;
  department_id: string;
  name: string;
  required_count: number;
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface TaskCategoryCreate {
  name: string;
  required_count: number;
  description?: string | null;
}

export interface TaskCategoryUpdate {
  name?: string;
  required_count?: number;
  description?: string | null;
  is_active?: boolean;
}
