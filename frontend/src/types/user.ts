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
	invite_code?: string;
}

export type PendingChangeStatus = "pending" | "approved" | "rejected";

export interface PendingChange {
	id: string;
	user_id: string;
	field_name: string;
	old_value: string | null;
	new_value: string | null;
	status: PendingChangeStatus;
	reviewed_by: string | null;
	reviewed_at: string | null;
	created_at: string;
}

export interface PendingChangeWithUser extends PendingChange {
	user_name: string;
	user_email: string;
}

export interface ChangePasswordRequest {
	current_password: string;
	new_password: string;
}

export interface ProfileUpdateRequest {
	full_name?: string;
	institutional_id?: string | null;
	department_id?: string | null;
}
