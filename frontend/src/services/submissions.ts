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
      body
    );
    return data;
  },

  async create(body: SubmissionCreate): Promise<Submission> {
    const { data } = await api.post<Submission>("/api/submissions", body);
    return data;
  },

  async list(params?: {
    department_id?: string;
    status?: string;
  }): Promise<Submission[]> {
    const { data } = await api.get<Submission[]>("/api/submissions", {
      params,
    });
    return data;
  },

  async get(id: string): Promise<Submission> {
    const { data } = await api.get<Submission>(`/api/submissions/${id}`);
    return data;
  },

  async review(id: string, body: SubmissionReview): Promise<Submission> {
    const { data } = await api.patch<Submission>(
      `/api/submissions/${id}/review`,
      body
    );
    return data;
  },

  async getProofUrl(id: string): Promise<string> {
    const { data } = await api.get<{ url: string }>(
      `/api/submissions/${id}/proof-url`
    );
    return data.url;
  },
};
