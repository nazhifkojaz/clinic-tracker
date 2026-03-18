import type { PaginatedResponse, PaginationParams } from "@/types/pagination";
import type {
	Submission,
	SubmissionCreate,
	SubmissionReview,
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

	get(id: string): Promise<Submission> {
		return api
			.get<Submission>(`/api/submissions/${id}`)
			.then((res) => res.data);
	},

	async review(id: string, body: SubmissionReview): Promise<Submission> {
		const { data } = await api.patch<Submission>(
			`/api/submissions/${id}/review`,
			body,
		);
		return data;
	},

	async getProofUrl(id: string): Promise<string> {
		const { data } = await api.get<{ url: string }>(
			`/api/submissions/${id}/proof-url`,
		);
		return data.url;
	},
};
