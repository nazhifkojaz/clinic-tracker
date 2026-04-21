import type { PaginatedResponse, PaginationParams } from "@/types/pagination";
import type {
	DeletedSubmission,
	Submission,
	SubmissionCreate,
	SubmissionReview,
	SubmissionUpdate,
	UploadUrlRequest,
	UploadUrlResponse,
} from "@/types/submission";
import api from "./api";

export const submissionService = {
	async getUploadUrl(body: UploadUrlRequest): Promise<UploadUrlResponse> {
		const { data } = await api.post<UploadUrlResponse>(
			"/api/submissions/upload-url",
			body,
		);
		return data;
	},

	async create(body: SubmissionCreate): Promise<Submission> {
		const { data } = await api.post<Submission>("/api/submissions", body);
		return data;
	},

	async update(id: string, body: SubmissionUpdate): Promise<Submission> {
		const { data } = await api.put<Submission>(`/api/submissions/${id}`, body);
		return data;
	},

	async list(
		params?: {
			department_id?: string;
			status?: string;
		} & PaginationParams,
	): Promise<PaginatedResponse<Submission>> {
		const { data } = await api.get<PaginatedResponse<Submission>>(
			"/api/submissions",
			{ params },
		);
		return data;
	},

	async review(id: string, body: SubmissionReview): Promise<Submission> {
		const { data } = await api.patch<Submission>(
			`/api/submissions/${id}/review`,
			body,
		);
		return data;
	},

	async getDeletedProofUrl(id: string): Promise<string> {
		const { data } = await api.get<{ url: string }>(
			`/api/submissions/${id}/deleted-proof-url`,
		);
		return data.url;
	},

	async getProofUrl(id: string): Promise<string> {
		const { data } = await api.get<{ url: string }>(
			`/api/submissions/${id}/proof-url`,
		);
		return data.url;
	},

	async delete(id: string): Promise<void> {
		await api.delete(`/api/submissions/${id}`);
	},

	async listDeleted(
		params?: PaginationParams,
	): Promise<PaginatedResponse<DeletedSubmission>> {
		const { data } = await api.get<PaginatedResponse<DeletedSubmission>>(
			"/api/submissions/deleted",
			{ params },
		);
		return data;
	},

	async restore(id: string): Promise<Submission> {
		const { data } = await api.post<Submission>(
			`/api/submissions/${id}/restore`,
		);
		return data;
	},
};
