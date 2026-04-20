import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import Login from "@/pages/Login";

const mockLogin = vi.hoisted(() => vi.fn());
const mockResendVerification = vi.hoisted(() => vi.fn());

vi.mock("@/stores/authStore", () => ({
	useAuthStore: () => ({
		login: mockLogin,
		isLoading: false,
	}),
}));

vi.mock("@/services/auth", () => ({
	authService: {
		resendVerification: mockResendVerification,
	},
}));

vi.mock("react-router-dom", async (importOriginal) => {
	const actual = await importOriginal<typeof import("react-router-dom")>();
	return { ...actual, useNavigate: () => vi.fn() };
});

describe("Login", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("renders identifier and password fields", () => {
		render(
			<MemoryRouter>
				<Login />
			</MemoryRouter>,
		);
		expect(screen.getByLabelText(/email or id/i)).toBeInTheDocument();
		expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
		expect(
			screen.getByRole("button", { name: /sign in/i }),
		).toBeInTheDocument();
	});

	it("allows typing in identifier and password", async () => {
		const user = userEvent.setup();
		render(
			<MemoryRouter>
				<Login />
			</MemoryRouter>,
		);

		const identifierInput = screen.getByLabelText(/email or id/i);
		const passwordInput = screen.getByLabelText(/password/i);

		await user.type(identifierInput, "test@example.com");
		await user.type(passwordInput, "password123");

		expect(identifierInput).toHaveValue("test@example.com");
		expect(passwordInput).toHaveValue("password123");
	});

	it("shows resend form when login returns unverified-email 403", async () => {
		const user = userEvent.setup();
		mockLogin.mockRejectedValue({
			response: {
				data: { detail: "Please verify your email before logging in." },
			},
		});

		render(
			<MemoryRouter>
				<Login />
			</MemoryRouter>,
		);

		await user.type(screen.getByLabelText(/email or id/i), "user@test.com");
		await user.type(screen.getByLabelText(/password/i), "wrongpass");
		await user.click(screen.getByRole("button", { name: /sign in/i }));

		await waitFor(() => {
			expect(screen.getByText(/resend verification email/i)).toBeInTheDocument();
		});
		// Email pre-filled because identifier looks like an email
		const resendInput = screen.getByPlaceholderText(/your@email\.com/i);
		expect(resendInput).toHaveValue("user@test.com");
	});

	it("does not show resend form for other login errors", async () => {
		const user = userEvent.setup();
		mockLogin.mockRejectedValue({
			response: { data: { detail: "Invalid credentials" } },
		});

		render(
			<MemoryRouter>
				<Login />
			</MemoryRouter>,
		);

		await user.type(screen.getByLabelText(/email or id/i), "user@test.com");
		await user.type(screen.getByLabelText(/password/i), "wrongpass");
		await user.click(screen.getByRole("button", { name: /sign in/i }));

		await waitFor(() => {
			expect(screen.getByText(/invalid credentials/i)).toBeInTheDocument();
		});
		expect(screen.queryByText(/resend verification email/i)).not.toBeInTheDocument();
	});

	it("sends resend request and shows confirmation", async () => {
		const user = userEvent.setup();
		mockLogin.mockRejectedValue({
			response: {
				data: { detail: "Please verify your email before logging in." },
			},
		});
		mockResendVerification.mockResolvedValue({ message: "Sent" });

		render(
			<MemoryRouter>
				<Login />
			</MemoryRouter>,
		);

		await user.type(screen.getByLabelText(/email or id/i), "user@test.com");
		await user.type(screen.getByLabelText(/password/i), "wrongpass");
		await user.click(screen.getByRole("button", { name: /sign in/i }));

		await waitFor(() => {
			expect(screen.getByRole("button", { name: /resend link/i })).toBeInTheDocument();
		});

		await user.click(screen.getByRole("button", { name: /resend link/i }));

		await waitFor(() => {
			expect(screen.getByText(/check your inbox/i)).toBeInTheDocument();
		});
		expect(mockResendVerification).toHaveBeenCalledWith("user@test.com");
	});
});
