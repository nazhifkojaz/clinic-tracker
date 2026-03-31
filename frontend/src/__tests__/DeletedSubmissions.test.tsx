import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import DeletedSubmissions from "@/pages/admin/DeletedSubmissions";

const mockListDeleted = vi.hoisted(() => vi.fn());

vi.mock("@/services/submissions", () => ({
	submissionService: {
		listDeleted: mockListDeleted,
		restore: vi.fn().mockResolvedValue({}),
	},
}));

vi.mock("@/services/departments", () => ({
	departmentService: {
		list: vi.fn().mockResolvedValue([]),
		listCategories: vi.fn().mockResolvedValue([]),
	},
}));

vi.mock("@/components/skeletons/TableSkeleton", () => ({
	TableSkeleton: () => <div data-testid="table-skeleton" />,
}));

function renderPage() {
	return render(
		<MemoryRouter>
			<DeletedSubmissions />
		</MemoryRouter>,
	);
}

describe("DeletedSubmissions", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("renders the page heading", async () => {
		mockListDeleted.mockResolvedValue({ items: [], total: 0, has_more: false });
		renderPage();
		await waitFor(() => {
			expect(
				screen.getByRole("heading", { name: /deleted submissions/i }),
			).toBeInTheDocument();
		});
	});

	it("shows empty state when there are no deleted submissions", async () => {
		mockListDeleted.mockResolvedValue({ items: [], total: 0, has_more: false });
		renderPage();
		await waitFor(() => {
			expect(screen.getByText(/no deleted submissions/i)).toBeInTheDocument();
		});
	});

	it("renders deleted submissions with a Restore button", async () => {
		mockListDeleted.mockResolvedValue({
			items: [
				{
					id: "sub-1",
					student_id: "user-1",
					student: { id: "user-1", full_name: "Jane Doe", student_id: "STU001", email: "jane@test.com" },
					department_id: "dept-1",
					task_category_id: "cat-1",
					case_count: 3,
					proof_key: "submissions/proof.jpg",
					notes: null,
					status: "pending",
					reviewed_by: null,
					reviewer: null,
					review_notes: null,
					created_at: "2026-03-01T00:00:00Z",
					updated_at: "2026-03-01T00:00:00Z",
					deleted_at: "2026-03-30T10:00:00Z",
					deleted_by_id: "admin-1",
					deleted_by_name: "Admin User",
				},
			],
			total: 1,
			has_more: false,
		});

		renderPage();

		await waitFor(() => {
			expect(screen.getByText("Jane Doe")).toBeInTheDocument();
		});
		expect(screen.getByRole("button", { name: /restore/i })).toBeInTheDocument();
		expect(screen.getByText("Admin User")).toBeInTheDocument();
	});
});
