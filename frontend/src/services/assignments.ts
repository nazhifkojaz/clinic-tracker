import type {
	Assignment,
	AssignmentCreate,
	AssignmentWithDetails,
} from "@/types/assignment";
import type { PaginatedResponse, PaginationParams } from "@/types/pagination";
import api from "./api";

export const assignmentService = {
	async list(
		params?: {
			assignment_type?: string;
			supervisor_id?: string;
			student_id?: string;
		} & PaginationParams,
	): Promise<PaginatedResponse<AssignmentWithDetails>> {
		const { data } = await api.get<PaginatedResponse<AssignmentWithDetails>>(
			"/api/assignments",
			{ params },
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
};
