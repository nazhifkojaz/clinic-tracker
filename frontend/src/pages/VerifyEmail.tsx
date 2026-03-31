import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { authService } from "@/services/auth";

type VerifyState = "loading" | "success" | "error";

export default function VerifyEmail() {
	const [searchParams] = useSearchParams();
	const [state, setState] = useState<VerifyState>("loading");
	const [message, setMessage] = useState("");

	useEffect(() => {
		const token = searchParams.get("token");
		if (!token) {
			setState("error");
			setMessage("No verification token provided.");
			return;
		}

		authService
			.verifyEmail(token)
			.then((res) => {
				setState("success");
				setMessage(res.message);
			})
			.catch(() => {
				setState("error");
				setMessage(
					"This verification link is invalid or has expired. Please register again.",
				);
			});
	}, [searchParams]);

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
						<CardContent className="text-center">
							<Link
								to="/register"
								className="text-sm font-medium text-primary hover:underline"
							>
								Register again
							</Link>
						</CardContent>
					</>
				)}
			</Card>
		</div>
	);
}
