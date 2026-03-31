import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import VerifyEmail from "@/pages/VerifyEmail";

const mockVerifyEmail = vi.hoisted(() => vi.fn());

vi.mock("@/services/auth", () => ({
	authService: {
		verifyEmail: mockVerifyEmail,
	},
}));

function renderWithToken(token?: string) {
	const initialEntry = token ? `/?token=${token}` : "/";
	return render(
		<MemoryRouter initialEntries={[initialEntry]}>
			<VerifyEmail />
		</MemoryRouter>,
	);
}

describe("VerifyEmail", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("shows loading state while verifying", () => {
		mockVerifyEmail.mockReturnValue(new Promise(() => {})); // never resolves
		renderWithToken("some-token");
		expect(screen.getByText(/verifying your email/i)).toBeInTheDocument();
	});

	it("shows success state after successful verification", async () => {
		mockVerifyEmail.mockResolvedValue({
			message: "Email verified. Your account is pending admin approval.",
		});
		renderWithToken("valid-token");

		// Wait for the "Go to Login" link that only appears in the success state
		await waitFor(() => {
			expect(screen.getByRole("link", { name: /go to login/i })).toBeInTheDocument();
		});
	});

	it("shows error state when verification fails", async () => {
		mockVerifyEmail.mockRejectedValue(new Error("Invalid token"));
		renderWithToken("bad-token");

		await waitFor(() => {
			expect(screen.getByText(/verification failed/i)).toBeInTheDocument();
		});
		expect(
			screen.getByRole("link", { name: /register again/i }),
		).toBeInTheDocument();
	});

	it("shows error state immediately when no token is in the URL", async () => {
		renderWithToken(); // no token

		await waitFor(() => {
			expect(screen.getByText(/verification failed/i)).toBeInTheDocument();
		});
		expect(mockVerifyEmail).not.toHaveBeenCalled();
	});
});
