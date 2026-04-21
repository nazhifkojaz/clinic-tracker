import type { AcademicSupervisor } from "@/types/submission";
import api from "./api";

export const studentService = {
	async getAcademicSupervisor(): Promise<AcademicSupervisor> {
		const { data } = await api.get<AcademicSupervisor>(
			"/api/students/me/academic-supervisor",
		);
		return data;
	},
};
