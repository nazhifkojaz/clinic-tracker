export type UserRole = "admin" | "supervisor" | "student";

export interface User {
  id: string;
  email: string;
  full_name: string;
  student_id: string | null;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface UserCreate {
  email: string;
  password: string;
  full_name: string;
  student_id?: string | null;
  role: UserRole;
}

export interface UserUpdate {
  email?: string;
  full_name?: string;
  student_id?: string | null;
  role?: UserRole;
  is_active?: boolean;
  password?: string;
}
