import type { User, UserCreate, UserUpdate } from "@/types/user";
import api from "./api";

export const userService = {
  async list(): Promise<User[]> {
    const { data } = await api.get<User[]>("/api/users");
    return data;
  },

  async create(user: UserCreate): Promise<User> {
    const { data } = await api.post<User>("/api/users", user);
    return data;
  },

  async update(id: string, user: UserUpdate): Promise<User> {
    const { data } = await api.patch<User>(`/api/users/${id}`, user);
    return data;
  },
};
