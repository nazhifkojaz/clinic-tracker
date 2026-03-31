import type { PaginatedResponse, PaginationParams } from "@/types/pagination";
import type { User, UserCreate, UserUpdate } from "@/types/user";
import api from "./api";

export const userService = {
	async list(
		params?: PaginationParams & {
			role?: string;
			is_active?: boolean;
			pending_approval?: boolean;
			search?: string;
		},
	): Promise<PaginatedResponse<User>> {
		const { data } = await api.get<PaginatedResponse<User>>("/api/users", {
			params,
		});
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
