import api from "./api";
import type {
  NotificationRecord,
  NotificationSend,
  NotificationStatus,
  NotificationTemplate,
} from "../types/notification";

export const notificationService = {
  async getTemplates(): Promise<NotificationTemplate[]> {
    const { data } = await api.get<NotificationTemplate[]>(
      "/api/notifications/templates"
    );
    return data;
  },

  async getStatus(): Promise<NotificationStatus> {
    const { data } = await api.get<NotificationStatus>(
      "/api/notifications/status"
    );
    return data;
  },

  async send(payload: NotificationSend): Promise<NotificationRecord[]> {
    const { data } = await api.post<NotificationRecord[]>(
      "/api/notifications/send",
      payload
    );
    return data;
  },

  async list(params?: {
    recipient_id?: string;
    limit?: number;
    offset?: number;
  }): Promise<NotificationRecord[]> {
    const { data } = await api.get<NotificationRecord[]>(
      "/api/notifications",
      { params }
    );
    return data;
  },
};
