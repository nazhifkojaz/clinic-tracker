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
