import type { PaginatedResponse, PaginationParams } from "@/types/pagination";
import type {
	ChangePasswordRequest,
	PendingChange,
	PendingChangeStatus,
	PendingChangeWithUser,
	ProfileUpdateRequest,
	User,
	UserCreate,
	UserUpdate,
} from "@/types/user";
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

	async delete(id: string, mode: "soft" | "hard"): Promise<void> {
		await api.delete(`/api/users/${id}`, { params: { mode } });
	},

	async changePassword(body: ChangePasswordRequest): Promise<void> {
		await api.post("/api/users/me/change-password", body);
	},

	async updateOwnProfile(body: ProfileUpdateRequest): Promise<User> {
		const { data } = await api.patch<User>("/api/users/me/profile", body);
		return data;
	},

	async getMyPendingChanges(): Promise<PendingChange[]> {
		const { data } = await api.get<PendingChange[]>(
			"/api/users/me/pending-changes",
		);
		return data;
	},

	async listPendingChanges(
		params?: PaginationParams & { status?: PendingChangeStatus },
	): Promise<PaginatedResponse<PendingChangeWithUser>> {
		const { data } = await api.get<PaginatedResponse<PendingChangeWithUser>>(
			"/api/users/pending-changes",
			{ params },
		);
		return data;
	},

	async approvePendingChange(changeId: string): Promise<void> {
		await api.post(`/api/users/pending-changes/${changeId}/approve`);
	},

	async rejectPendingChange(changeId: string): Promise<void> {
		await api.post(`/api/users/pending-changes/${changeId}/reject`);
	},
};
