import type { NotificationRecord } from "@/types/notification";
import api from "./api";

export const notificationService = {
	async list(params?: {
		recipient_id?: string;
		limit?: number;
		offset?: number;
	}): Promise<NotificationRecord[]> {
		const { data } = await api.get<NotificationRecord[]>("/api/notifications", {
			params,
		});
		return data;
	},
};
