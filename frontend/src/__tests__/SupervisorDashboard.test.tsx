import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import SupervisorDashboard from "@/pages/SupervisorDashboard";

const mockStudents = [
  {
    student_id: "1",
    student_name: "John Doe",
    student_code: "STU001",
    student_email: "john@example.com",
    current_department: "Oral Surgery",
    overall_completion_percentage: 75.5,
    total_required: 100,
    total_completed: 75,
    status: "on_track",
  },
];

vi.mock("@/services/dashboard", () => ({
  dashboardService: {
    getSupervisorDashboard: vi.fn(() =>
      Promise.resolve({
        total_students: 1,
        on_track_count: 1,
        at_risk_count: 0,
        behind_count: 0,
        students: mockStudents,
      })
    ),
    getStudentDashboardById: vi.fn(() =>
      Promise.resolve({
        student_id: "1",
        student_name: "John Doe",
        current_department: "Oral Surgery",
        overall_completion_percentage: 75.5,
        total_required: 100,
        total_completed: 75,
        departments: [],
        recent_submissions: [],
        progress_over_time: [],
      })
    ),
  },
}));

vi.mock("@/stores/authStore", () => ({
  useAuthStore: () => ({
    user: { id: "1", role: "supervisor", full_name: "Test Supervisor" },
  }),
}));

describe("SupervisorDashboard", () => {
  it("renders without crashing", () => {
    render(<MemoryRouter><SupervisorDashboard /></MemoryRouter>);
    expect(screen.queryByText(/something went wrong/i)).not.toBeInTheDocument();
  });

  it("renders table with correct column count", async () => {
    render(<MemoryRouter><SupervisorDashboard /></MemoryRouter>);
    expect(await screen.findByText("John Doe")).toBeInTheDocument();

    const headers = screen.getAllByRole("columnheader");
    expect(headers).toHaveLength(5);
  });

  it("displays progress bar with percentage in correct column", async () => {
    render(<MemoryRouter><SupervisorDashboard /></MemoryRouter>);
    expect(await screen.findByText("75.5%")).toBeInTheDocument();

    const studentRow = screen.getByText("John Doe").closest("tr");
    if (studentRow) {
      const cells = within(studentRow).getAllByRole("cell");
      expect(cells[2]).toHaveTextContent("75.5%");
      expect(cells[1]).toHaveTextContent("Oral Surgery");
    }
  });
});
