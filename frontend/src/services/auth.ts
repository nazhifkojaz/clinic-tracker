import type { LoginRequest, TokenResponse } from "@/types/auth";
import type { User } from "@/types/user";
import api from "./api";

export const authService = {
  async login(credentials: LoginRequest): Promise<TokenResponse> {
    const { data } = await api.post<TokenResponse>("/api/auth/login", credentials);
    return data;
  },

  async refresh(refreshToken: string): Promise<TokenResponse> {
    const { data } = await api.post<TokenResponse>("/api/auth/refresh", {
      refresh_token: refreshToken,
    });
    return data;
  },

  async getMe(): Promise<User> {
    const { data } = await api.get<User>("/api/users/me");
    return data;
  },
};
