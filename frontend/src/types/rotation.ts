export interface Rotation {
  id: string;
  student_id: string;
  department_id: string;
  is_current: boolean;
  started_at: string;
  ended_at: string | null;
}

export interface RotationCreate {
  department_id: string;
}
