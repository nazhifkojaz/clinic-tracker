// frontend/src/services/dashboard.ts

import type {
  StudentDashboardData,
  SupervisorDashboardData,
  DepartmentDashboardData,
} from "@/types/dashboard";
import api from "./api";

export const dashboardService = {
  async getStudentDashboard(): Promise<StudentDashboardData> {
    const { data } = await api.get<StudentDashboardData>("/api/dashboard/student");
    return data;
  },

  async getStudentDashboardById(studentId: string): Promise<StudentDashboardData> {
    const { data } = await api.get<StudentDashboardData>(
      `/api/dashboard/student/${studentId}`
    );
    return data;
  },

  async getSupervisorDashboard(): Promise<SupervisorDashboardData> {
    const { data } = await api.get<SupervisorDashboardData>(
      "/api/dashboard/supervisor"
    );
    return data;
  },

  async getDepartmentDashboard(departmentId: string): Promise<DepartmentDashboardData> {
    const { data } = await api.get<DepartmentDashboardData>(
      `/api/dashboard/department/${departmentId}`
    );
    return data;
  },
};
