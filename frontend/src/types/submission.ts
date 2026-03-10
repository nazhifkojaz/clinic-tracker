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
  proof_url: string;
  notes: string | null;
  status: SubmissionStatus;
  reviewed_by: string | null;
  reviewer?: ReviewerInfo;
  review_notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface SubmissionCreate {
  department_id: string;
  task_category_id: string;
  case_count: number;
  proof_url: string;
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
