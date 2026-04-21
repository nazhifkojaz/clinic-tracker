// frontend/src/types/dashboard.ts

import type { PaginatedResponse } from "./pagination";

export interface CategoryProgress {
	category_id: string;
	category_name: string;
	required_count: number;
	completed_count: number;
	pending_count: number;
	completion_percentage: number;
}

export interface DepartmentProgress {
	department_id: string;
	department_name: string;
	categories: CategoryProgress[];
	total_required: number;
	total_completed: number;
	completion_percentage: number;
}

export interface RecentSubmission {
	id: string;
	department_name: string;
	category_name: string;
	case_count: number;
	status: string;
	created_at: string;
}

export interface ProgressDataPoint {
	date: string;
	cumulative_cases: number;
}

export interface StudentDashboardData {
	student_id: string;
	student_name: string;
	current_department: string | null;
	overall_completion_percentage: number;
	total_required: number;
	total_completed: number;
	departments: DepartmentProgress[];
	recent_submissions: RecentSubmission[];
	progress_over_time: ProgressDataPoint[];
	show_rotation_warning: boolean;
	rotation_days_active: number;
	rotation_duration_days: number;
	rotation_time_pct: number;
}

export type StudentStatus = "on_track" | "at_risk" | "unassigned";

export interface StudentSummary {
	student_id: string;
	student_name: string;
	student_email: string;
	student_code: string | null;
	current_department: string | null;
	overall_completion_percentage: number;
	total_required: number;
	total_completed: number;
	status: StudentStatus;
	assignment_type: "primary" | "department" | null;
}

export interface SupervisorDashboardData {
	total_students: number;
	on_track_count: number;
	at_risk_count: number;
	unassigned_count: number;
	students: PaginatedResponse<StudentSummary>;
}

// --- Rotation Tracker Types ---

export type CaseStatusColor = "red" | "yellow" | "green";

export interface DepartmentTrackerEntry {
	department_id: string;
	department_name: string;
	is_current: boolean;
	total_required: number;
	total_completed: number;
	total_pending: number;
	case_completion_percentage: number;
	case_status_color: CaseStatusColor;
	rotation_duration_days: number;
	days_active: number;
	time_completion_percentage: number;
	started_at: string | null;
	rotation_id: string | null;
}

export interface DepartmentTrackerData {
	current_department_id: string | null;
	entries: DepartmentTrackerEntry[];
	show_warning: boolean;
}
