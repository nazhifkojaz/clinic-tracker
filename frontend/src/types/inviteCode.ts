export type InviteCodeStatus = "active" | "used";

export interface InviteCode {
	id: string;
	code: string;
	status: InviteCodeStatus;
	used_by: string | null;
	used_at: string | null;
	created_at: string;
}
