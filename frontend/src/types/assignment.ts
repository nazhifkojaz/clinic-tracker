export type AssignmentType = "primary" | "department";

export interface Assignment {
  id: string;
  supervisor_id: string;
  student_id: string | null;
  assignment_type: AssignmentType;
  department_id: string | null;
  created_at: string;
}

export interface AssignmentWithDetails extends Assignment {
  supervisor_name: string;
  student_name: string | null;
  department_name: string | null;
}

export interface AssignmentCreate {
  supervisor_id: string;
  student_id?: string | null;
  assignment_type: AssignmentType;
  department_id?: string | null;
}

export interface MyStudent {
  assignment_id: string;
  student_id: string;
  student_name: string;
  student_email: string;
  student_code: string | null;
  assignment_type: AssignmentType;
  department_id: string | null;
  department_name: string | null;
}
