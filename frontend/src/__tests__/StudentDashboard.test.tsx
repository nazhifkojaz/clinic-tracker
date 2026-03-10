import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import StudentDashboard from "@/pages/StudentDashboard";

// Mock the dashboard service
vi.mock("@/services/dashboard", () => ({
  dashboardService: {
    getStudentDashboard: vi.fn(() =>
      Promise.resolve({
        overall_completion_percentage: 50,
        departments: [],
        progress_over_time: [],
      })
    ),
  },
}));

// Mock the auth store
vi.mock("@/stores/authStore", () => ({
  useAuthStore: () => ({
    user: { id: "1", role: "student", full_name: "Test Student" },
  }),
}));

describe("StudentDashboard", () => {
  it("renders without crashing", () => {
    render(
      <MemoryRouter>
        <StudentDashboard />
      </MemoryRouter>
    );
    // Dashboard shows loading skeleton initially
    expect(screen.queryByText(/something went wrong/i)).not.toBeInTheDocument();
  });
});
