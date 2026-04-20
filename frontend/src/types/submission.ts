export type SubmissionStatus = "pending" | "approved" | "rejected";

export interface StudentInfo {
	id: string;
	full_name: string;
	student_id: string | null;
	email: string;
}

export interface ReviewerInfo {
	id: string;
	full_name: string;
}

export interface Submission {
	id: string;
	student_id: string;
	student?: StudentInfo;
	department_id: string;
	task_category_id: string;
	case_count: number;
	notes: string | null;
	status: SubmissionStatus;
	target_supervisor_id: string | null;
	target_supervisor: ReviewerInfo | null;
	reviewed_by: string | null;
	reviewer?: ReviewerInfo;
	review_notes: string | null;
	can_review: boolean;
	created_at: string;
	updated_at: string;
	deleted_at: string | null;
}

export interface DeletedSubmission extends Submission {
	deleted_by_id: string | null;
	deleted_by_name: string | null;
}

export interface SubmissionCreate {
	department_id: string;
	target_supervisor_id: string;
	task_category_id: string;
	case_count: number;
	proof_key: string;
	notes?: string | null;
}

export interface SubmissionUpdate {
	case_count?: number;
	proof_key?: string;
	notes?: string | null;
}

export interface SubmissionReview {
	status: "approved" | "rejected";
	review_notes?: string | null;
}

export interface UploadUrlRequest {
	filename: string;
	content_type: string;
}

export interface UploadUrlResponse {
	upload_url: string;
	object_key: string;
}

export interface DepartmentSupervisor {
	id: string;
	full_name: string;
}

export interface AcademicSupervisor {
	supervisor: ReviewerInfo | null;
}
