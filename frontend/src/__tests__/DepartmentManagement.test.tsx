import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import DepartmentManagement from "@/pages/admin/DepartmentManagement";

const mockDepartments = [
  {
    id: "1",
    name: "Oral Surgery",
    description: "Surgical procedures",
    is_active: true,
    category_count: 5,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
  },
  {
    id: "2",
    name: "Orthodontics",
    description: "Teeth alignment",
    is_active: true,
    category_count: 0,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
  },
];

vi.mock("@/services/departments", () => ({
  departmentService: {
    list: vi.fn(() => Promise.resolve(mockDepartments)),
    get: vi.fn(() => Promise.resolve({ task_categories: [] })),
  },
}));

vi.mock("@/stores/authStore", () => ({
  useAuthStore: () => ({
    user: { id: "1", role: "admin", full_name: "Test Admin" },
  }),
}));

describe("DepartmentManagement", () => {
  it("renders department list with category counts", async () => {
    render(
      <MemoryRouter>
        <DepartmentManagement />
      </MemoryRouter>
    );

    expect(await screen.findByText("Oral Surgery")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("0")).toBeInTheDocument();
  });

  it("shows dash for undefined category_count", async () => {
    const noCountDepts = [{ ...mockDepartments[0], category_count: undefined as unknown as number }];
    const { departmentService } = await import("@/services/departments");
    departmentService.list = vi.fn(() => Promise.resolve(noCountDepts));

    render(
      <MemoryRouter>
        <DepartmentManagement />
      </MemoryRouter>
    );

    expect(await screen.findByText("—")).toBeInTheDocument();
  });

  it("renders Fragment with key for each department", async () => {
    const { container } = render(
      <MemoryRouter>
        <DepartmentManagement />
      </MemoryRouter>
    );

    await screen.findByText("Oral Surgery");
    const rows = container.querySelectorAll("tbody tr");
    expect(rows.length).toBeGreaterThan(0);
  });
});
