import type { Rotation, RotationCreate } from "@/types/rotation";
import api from "./api";

export const rotationService = {
  async getCurrent(): Promise<Rotation | null> {
    const { data } = await api.get<Rotation | null>("/api/rotations/current");
    return data;
  },

  async set(body: RotationCreate): Promise<Rotation> {
    const { data } = await api.post<Rotation>("/api/rotations", body);
    return data;
  },

  async getHistory(): Promise<Rotation[]> {
    const { data } = await api.get<Rotation[]>("/api/rotations/history");
    return data;
  },

  async getStudentCurrent(studentId: string): Promise<Rotation | null> {
    const { data } = await api.get<Rotation | null>(
      `/api/rotations/students/${studentId}/current`
    );
    return data;
  },
};
