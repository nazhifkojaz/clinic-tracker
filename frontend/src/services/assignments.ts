import type {
  Assignment,
  AssignmentCreate,
  AssignmentWithDetails,
  MyStudent,
} from "@/types/assignment";
import api from "./api";

export const assignmentService = {
  async list(params?: {
    assignment_type?: string;
    supervisor_id?: string;
    student_id?: string;
  }): Promise<AssignmentWithDetails[]> {
    const { data } = await api.get<AssignmentWithDetails[]>(
      "/api/assignments",
      { params }
    );
    return data;
  },

  async create(body: AssignmentCreate): Promise<Assignment> {
    const { data } = await api.post<Assignment>("/api/assignments", body);
    return data;
  },

  async remove(id: string): Promise<void> {
    await api.delete(`/api/assignments/${id}`);
  },

  async getMyStudents(): Promise<MyStudent[]> {
    const { data } = await api.get<MyStudent[]>("/api/assignments/my-students");
    return data;
  },
};
