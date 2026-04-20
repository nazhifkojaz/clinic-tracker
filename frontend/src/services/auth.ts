import type { LoginRequest, TokenResponse } from "@/types/auth";
import type { User, UserRegisterRequest } from "@/types/user";
import api from "./api";

export const authService = {
	async login(credentials: LoginRequest): Promise<TokenResponse> {
		const { data } = await api.post<TokenResponse>(
			"/api/auth/login",
			credentials,
		);
		return data;
	},

	async getMe(): Promise<User> {
		const { data } = await api.get<User>("/api/users/me");
		return data;
	},

	async register(body: UserRegisterRequest): Promise<{ message: string }> {
		const { data } = await api.post<{ message: string }>(
			"/api/auth/register",
			body,
		);
		return data;
	},

	async verifyEmail(token: string): Promise<{ message: string }> {
		const { data } = await api.get<{ message: string }>(
			"/api/auth/verify-email",
			{ params: { token } },
		);
		return data;
	},

	async resendVerification(email: string): Promise<{ message: string }> {
		const { data } = await api.post<{ message: string }>(
			"/api/auth/resend-verification",
			{ email },
		);
		return data;
	},
};
