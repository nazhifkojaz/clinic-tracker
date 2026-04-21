import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import Register from "@/pages/Register";

vi.mock("@/services/auth", () => ({
	authService: {
		register: vi.fn().mockResolvedValue({}),
	},
}));

vi.mock("@/services/departments", () => ({
	departmentService: {
		list: vi.fn().mockResolvedValue([
			{ id: "dept-1", name: "Internal Medicine", is_active: true },
		]),
	},
}));

function renderRegister() {
	return render(
		<MemoryRouter>
			<Register />
		</MemoryRouter>,
	);
}

describe("Register", () => {
	it("renders all required form fields", () => {
		renderRegister();
		expect(screen.getByLabelText(/full name/i)).toBeInTheDocument();
		expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
		expect(screen.getByLabelText(/^role$/i)).toBeInTheDocument();
		expect(screen.getByLabelText(/^password$/i)).toBeInTheDocument();
		expect(screen.getByLabelText(/confirm password/i)).toBeInTheDocument();
	});

	it("includes admin, student, and supervisor as selectable roles", () => {
		renderRegister();
		const roleSelect = screen.getByLabelText(/^role$/i);
		const options = Array.from((roleSelect as HTMLSelectElement).options).map(
			(o) => o.value,
		);
		expect(options).toContain("admin");
		expect(options).toContain("student");
		expect(options).toContain("supervisor");
	});

	it("shows department field only when supervisor role is selected", async () => {
		const user = userEvent.setup();
		renderRegister();

		// No department field initially (student is default)
		expect(screen.queryByLabelText(/department/i)).not.toBeInTheDocument();

		// Switch to supervisor
		await user.selectOptions(screen.getByLabelText(/^role$/i), "supervisor");
		await waitFor(() => {
			expect(screen.getByLabelText(/department/i)).toBeInTheDocument();
		});

		// Switch back to student — department field disappears
		await user.selectOptions(screen.getByLabelText(/^role$/i), "student");
		await waitFor(() => {
			expect(screen.queryByLabelText(/department/i)).not.toBeInTheDocument();
		});
	});

	it("changes the ID field label based on selected role", async () => {
		const user = userEvent.setup();
		renderRegister();

		// Default: student → "Student ID"
		expect(screen.getByLabelText(/student id/i)).toBeInTheDocument();

		// Switch to supervisor → "Staff ID"
		await user.selectOptions(screen.getByLabelText(/^role$/i), "supervisor");
		await waitFor(() => {
			expect(screen.getByLabelText(/staff id/i)).toBeInTheDocument();
		});
	});

	it("shows a sign-in link", () => {
		renderRegister();
		expect(screen.getByRole("link", { name: /sign in/i })).toBeInTheDocument();
	});
});
