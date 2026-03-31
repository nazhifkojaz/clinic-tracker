export type UserRole = "admin" | "supervisor" | "student";

export interface User {
	id: string;
	email: string;
	full_name: string;
	institutional_id: string | null;
	department_id: string | null;
	role: UserRole;
	is_active: boolean;
	email_verified: boolean;
	created_at: string;
	updated_at: string;
}

export interface UserCreate {
	email: string;
	password: string;
	full_name: string;
	institutional_id?: string | null;
	department_id?: string | null;
	role: UserRole;
}

export interface UserUpdate {
	email?: string;
	full_name?: string;
	institutional_id?: string | null;
	department_id?: string | null;
	role?: UserRole;
	is_active?: boolean;
	password?: string;
}

export interface UserRegisterRequest {
	email: string;
	password: string;
	full_name: string;
	role: UserRole;
	institutional_id: string;
	department_id?: string | null;
}
