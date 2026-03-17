/**
 * Paginated response structure from the backend API.
 */
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

/**
 * Pagination parameters for API requests.
 */
export interface PaginationParams {
  limit?: number;
  offset?: number;
}
