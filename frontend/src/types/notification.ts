export interface NotificationTemplate {
  key: string;
  subject: string;
  message: string;
}

export interface NotificationSend {
  recipient_ids: string[];
  subject: string;
  message: string;
  template_key?: string;
  template_vars?: Record<string, string>;
}

export interface NotificationRecord {
  id: string;
  sender_id: string;
  sender_name: string;
  recipient_id: string;
  recipient_name: string;
  subject: string;
  message: string;
  sent_at: string;
}

export interface NotificationStatus {
  email_enabled: boolean;
  mode: "mock" | "production";
}
