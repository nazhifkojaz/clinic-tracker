import type { PaginatedResponse, PaginationParams } from "@/types/pagination";
import type {
	DayAdjustmentRequest,
	DepartmentOverrideRequest,
	Rotation,
	RotationCreate,
} from "@/types/rotation";
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

	async getHistory(
		params?: PaginationParams,
	): Promise<PaginatedResponse<Rotation>> {
		const { data } = await api.get<PaginatedResponse<Rotation>>(
			"/api/rotations/history",
			{ params },
		);
		return data;
	},

	async getStudentCurrent(studentId: string): Promise<Rotation | null> {
		const { data } = await api.get<Rotation | null>(
			`/api/rotations/students/${studentId}/current`,
		);
		return data;
	},

	async overrideDepartment(
		studentId: string,
		body: DepartmentOverrideRequest,
	): Promise<Rotation> {
		const { data } = await api.post<Rotation>(
			`/api/rotations/students/${studentId}/override-department`,
			body,
		);
		return data;
	},

	async adjustDay(studentId: string, totalDay: number): Promise<Rotation> {
		const { data } = await api.patch<Rotation>(
			`/api/rotations/students/${studentId}/day`,
			{ total_day: totalDay },
		);
		return data;
	},
};
