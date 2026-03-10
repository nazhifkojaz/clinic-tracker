import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import CaseInputForm from "@/pages/CaseInputForm";

// Mock the services to avoid API calls
vi.mock("@/services/departments", () => ({
  departmentService: {
    list: vi.fn().mockResolvedValue([]),
    listCategories: vi.fn().mockResolvedValue([]),
  },
}));
vi.mock("@/services/rotations", () => ({
  rotationService: {
    getCurrent: vi.fn().mockResolvedValue(null),
  },
}));
vi.mock("@/services/submissions", () => ({
  submissionService: {
    create: vi.fn().mockResolvedValue({}),
  },
}));

// Mock the auth store
vi.mock("@/stores/authStore", () => ({
  useAuthStore: () => ({
    user: { id: "1", role: "student", full_name: "Test Student" },
  }),
}));

describe("CaseInputForm", () => {
  it("renders the page title", async () => {
    render(
      <MemoryRouter>
        <CaseInputForm />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByText(/Submit Case Record/i)).toBeInTheDocument();
    });
  });
});
