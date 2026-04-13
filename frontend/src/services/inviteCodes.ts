import type { InviteCode } from "@/types/inviteCode";
import api from "./api";

export const inviteCodeService = {
	async generate(): Promise<InviteCode> {
		const { data } = await api.post<InviteCode>("/api/invite-codes");
		return data;
	},

	async list(): Promise<InviteCode[]> {
		const { data } = await api.get<InviteCode[]>("/api/invite-codes");
		return data;
	},

	async validate(code: string): Promise<{ valid: boolean }> {
		const { data } = await api.post<{ valid: boolean }>(
			"/api/invite-codes/validate",
			{ code },
		);
		return data;
	},
};
