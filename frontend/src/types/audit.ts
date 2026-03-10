export interface AuditLogEntry {
  id: string;
  user_id: string | null;
  user_name: string | null;
  action: string;
  table_name: string;
  record_id: string;
  old_values: Record<string, unknown> | null;
  new_values: Record<string, unknown> | null;
  created_at: string;
}

export interface AuditLogListResponse {
  items: AuditLogEntry[];
  total: number;
}

export interface AuditLogMetadata {
  actions: string[];
  table_names: string[];
}
