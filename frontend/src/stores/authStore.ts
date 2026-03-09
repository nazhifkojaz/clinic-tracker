import { create } from "zustand";
import type { User } from "@/types/user";
import { authService } from "@/services/auth";

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isInitialized: boolean;
  isLoading: boolean;

  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  initialize: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: false,
  isInitialized: false,
  isLoading: false,

  login: async (email: string, password: string) => {
    set({ isLoading: true });
    try {
      const tokens = await authService.login({ email, password });
      localStorage.setItem("access_token", tokens.access_token);
      localStorage.setItem("refresh_token", tokens.refresh_token);

      const user = await authService.getMe();
      set({ user, isAuthenticated: true, isLoading: false });
    } catch (error) {
      set({ isLoading: false });
      throw error;
    }
  },

  logout: () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    set({ user: null, isAuthenticated: false });
  },

  initialize: async () => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      set({ isInitialized: true });
      return;
    }
    try {
      const user = await authService.getMe();
      set({ user, isAuthenticated: true, isInitialized: true });
    } catch {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      set({ isInitialized: true });
    }
  },
}));
