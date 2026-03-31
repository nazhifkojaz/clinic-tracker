export interface LoginRequest {
	identifier: string; // accepts email address or institutional_id
	password: string;
}

export interface TokenResponse {
	access_token: string;
	refresh_token: string;
	token_type: string;
}
