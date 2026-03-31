export interface Rotation {
	id: string;
	student_id: string;
	department_id: string;
	is_current: boolean;
	started_at: string;
	ended_at: string | null;
	days_offset: number;
}

export interface RotationCreate {
	department_id: string;
	days_offset?: number;
}

export interface DepartmentOverrideRequest {
	department_id: string;
}
