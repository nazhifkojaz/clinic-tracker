import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import CaseInputForm from "@/pages/CaseInputForm";

// Mock the services to avoid API calls
vi.mock("@/services/departments");
vi.mock("@/services/rotations");
vi.mock("@/services/submissions");

// Mock the auth store
vi.mock("@/stores/authStore", () => ({
  useAuthStore: () => ({
    user: { id: "1", role: "student", full_name: "Test Student" },
  }),
}));

describe("CaseInputForm", () => {
  it("renders the page title", () => {
    render(
      <MemoryRouter>
        <CaseInputForm />
      </MemoryRouter>
    );
    expect(screen.getByText(/Submit Case Record/i)).toBeInTheDocument();
  });
});
