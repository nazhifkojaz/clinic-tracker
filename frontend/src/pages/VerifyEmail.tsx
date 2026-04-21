import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { authService } from "@/services/auth";

type VerifyState = "loading" | "success" | "error";
type ResendState = "idle" | "loading" | "sent" | "error";

export default function VerifyEmail() {
	const [searchParams] = useSearchParams();
	const token = searchParams.get("token");
	const [state, setState] = useState<VerifyState>(token ? "loading" : "error");
	const [message, setMessage] = useState(
		token ? "" : "No verification token provided.",
	);

	const [resendEmail, setResendEmail] = useState("");
	const [resendState, setResendState] = useState<ResendState>("idle");

	useEffect(() => {
		if (!token) return;

		authService
			.verifyEmail(token)
			.then((res) => {
				setState("success");
				setMessage(res.message);
			})
			.catch(() => {
				setState("error");
				setMessage("This verification link is invalid or has expired.");
			});
	}, [token]);

	const handleResend = async (e: React.FormEvent) => {
		e.preventDefault();
		setResendState("loading");
		try {
			await authService.resendVerification(resendEmail);
			setResendState("sent");
		} catch {
			setResendState("error");
		}
	};

	return (
		<div className="flex min-h-screen items-center justify-center bg-background px-4">
			<Card className="w-full max-w-sm">
				{state === "loading" && (
					<CardContent className="flex flex-col items-center justify-center py-12">
						<div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
						<p className="mt-4 text-sm text-muted-foreground">
							Verifying your email...
						</p>
					</CardContent>
				)}
				{state === "success" && (
					<>
						<CardHeader className="text-center">
							<CardTitle className="text-2xl">Email verified!</CardTitle>
							<CardDescription>{message}</CardDescription>
						</CardHeader>
						<CardContent className="text-center">
							<Link
								to="/login"
								className="text-sm font-medium text-primary hover:underline"
							>
								Go to Login
							</Link>
						</CardContent>
					</>
				)}
				{state === "error" && (
					<>
						<CardHeader className="text-center">
							<CardTitle className="text-2xl">Verification failed</CardTitle>
							<CardDescription>{message}</CardDescription>
						</CardHeader>
						<CardContent className="space-y-4">
							{resendState === "sent" ? (
								<p className="text-center text-sm text-muted-foreground">
									Check your inbox for a new verification link.
								</p>
							) : (
								<form onSubmit={handleResend} className="space-y-3">
									<p className="text-center text-sm text-muted-foreground">
										Enter your email to get a new link:
									</p>
									<Input
										type="email"
										placeholder="your@email.com"
										value={resendEmail}
										onChange={(e) => setResendEmail(e.target.value)}
										required
									/>
									{resendState === "error" && (
										<p className="text-center text-sm text-destructive">
											Something went wrong. Please try again.
										</p>
									)}
									<Button
										type="submit"
										className="w-full"
										disabled={resendState === "loading"}
									>
										{resendState === "loading"
											? "Sending..."
											: "Resend verification email"}
									</Button>
								</form>
							)}
							<div className="text-center">
								<Link
									to="/login"
									className="text-sm font-medium text-primary hover:underline"
								>
									Back to Login
								</Link>
							</div>
						</CardContent>
					</>
				)}
			</Card>
		</div>
	);
}
