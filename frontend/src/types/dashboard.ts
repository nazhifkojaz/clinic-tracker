// frontend/src/types/dashboard.ts

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
}

export type StudentStatus = "on_track" | "at_risk" | "behind";

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
}

export interface SupervisorDashboardData {
  total_students: number;
  on_track_count: number;
  at_risk_count: number;
  behind_count: number;
  students: StudentSummary[];
}

export interface DepartmentStudentProgress {
  student_id: string;
  student_name: string;
  total_required: number;
  total_completed: number;
  completion_percentage: number;
  status: string;
}

export interface DepartmentDashboardData {
  department_id: string;
  department_name: string;
  total_students: number;
  average_completion: number;
  students: DepartmentStudentProgress[];
}
