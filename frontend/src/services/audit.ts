import api from "./api";
import type { AuditLogListResponse, AuditLogMetadata } from "../types/audit";

export const auditService = {
  async list(params?: {
    user_id?: string;
    action?: string;
    table_name?: string;
    date_from?: string;
    date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<AuditLogListResponse> {
    const { data } = await api.get<AuditLogListResponse>(
      "/api/admin/audit-logs",
      { params }
    );
    return data;
  },

  async getMetadata(): Promise<AuditLogMetadata> {
    const { data } = await api.get<AuditLogMetadata>(
      "/api/admin/audit-logs/metadata"
    );
    return data;
  },
};
