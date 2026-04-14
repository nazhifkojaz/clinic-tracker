import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { authService } from "@/services/auth";
import { departmentService } from "@/services/departments";
import type { Department } from "@/types/department";
import type { UserRole } from "@/types/user";

export default function Register() {
	const [formData, setFormData] = useState({
		email: "",
		password: "",
		confirmPassword: "",
		full_name: "",
		role: "student" as UserRole,
		institutional_id: "",
		department_id: "",
		invite_code: "",
	});
	const [departments, setDepartments] = useState<Department[]>([]);
	const [isSubmitting, setIsSubmitting] = useState(false);
	const [error, setError] = useState("");
	const [success, setSuccess] = useState(false);

	useEffect(() => {
		departmentService
			.list()
			.then((depts) => setDepartments(depts.filter((d) => d.is_active)))
			.catch(() => {});
	}, []);

	const idLabel =
		formData.role === "student" ? "Student ID"
		: formData.role === "admin" ? "Admin ID"
		: "Staff ID";

	const handleSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		setError("");

		if (formData.password !== formData.confirmPassword) {
			setError("Passwords do not match.");
			return;
		}
		if (!formData.institutional_id.trim()) {
			setError(`${idLabel} is required.`);
			return;
		}
		if (formData.role === "admin" && !formData.invite_code.trim()) {
			setError("Invite code is required for admin registration.");
			return;
		}

		setIsSubmitting(true);
		try {
			await authService.register({
				email: formData.email,
				password: formData.password,
				full_name: formData.full_name,
				role: formData.role,
				institutional_id: formData.institutional_id,
				department_id:
					formData.role === "supervisor" && formData.department_id
						? formData.department_id
						: null,
				invite_code:
					formData.role === "admin" && formData.invite_code
						? formData.invite_code.trim()
						: undefined,
			});
			setSuccess(true);
		} catch (err: unknown) {
			const response = (err as { response?: { status?: number; data?: { detail?: string } } })?.response;
			if (response?.status === 409) {
				setError("Email or institutional ID is already registered.");
			} else if (response?.status === 400 && response.data?.detail) {
				setError(response.data.detail);
			} else {
				setError("Registration failed. Please try again.");
			}
		} finally {
			setIsSubmitting(false);
		}
	};

	if (success) {
		return (
			<div className="flex min-h-screen items-center justify-center bg-background px-4">
				<Card className="w-full max-w-sm">
					<CardHeader className="text-center">
						<CardTitle className="text-2xl">Check your email</CardTitle>
						<CardDescription>
							Registration successful! We've sent a verification link to{" "}
							<strong>{formData.email}</strong>. Please click the link to verify
							your account before logging in.
						</CardDescription>
					</CardHeader>
					<CardContent>
						<p className="text-center text-sm text-muted-foreground">
							After verification, your account will be reviewed by an admin.
						</p>
						<div className="mt-4 text-center">
							<Link
								to="/login"
								className="text-sm font-medium text-primary hover:underline"
							>
								Back to Login
							</Link>
						</div>
					</CardContent>
				</Card>
			</div>
		);
	}

	return (
		<div className="flex min-h-screen items-center justify-center bg-background px-4">
			<Card className="w-full max-w-md">
				<CardHeader className="text-center">
					<CardTitle className="text-2xl">Create an account</CardTitle>
					<CardDescription>
						Register for Smart Clinic Tracker
					</CardDescription>
				</CardHeader>
				<CardContent>
					<form onSubmit={handleSubmit} className="space-y-4">
						{error && (
							<div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
								{error}
							</div>
						)}
						<div className="space-y-2">
							<Label htmlFor="full_name">Full Name</Label>
							<Input
								id="full_name"
								value={formData.full_name}
								onChange={(e) =>
									setFormData({ ...formData, full_name: e.target.value })
								}
								required
							/>
						</div>
						<div className="space-y-2">
							<Label htmlFor="email">Email</Label>
							<Input
								id="email"
								type="email"
								value={formData.email}
								onChange={(e) =>
									setFormData({ ...formData, email: e.target.value })
								}
								required
							/>
						</div>
						<div className="space-y-2">
							<Label htmlFor="role">Role</Label>
							<select
								id="role"
								className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm"
								value={formData.role}
								onChange={(e) =>
									setFormData({
										...formData,
										role: e.target.value as UserRole,
										department_id: "",
									})
								}
							>
								<option value="student">Student</option>
								<option value="supervisor">Supervisor</option>
								<option value="admin">Admin</option>
							</select>
						</div>
						{formData.role === "admin" && (
							<div className="space-y-2">
								<Label htmlFor="invite_code">Invite Code</Label>
								<Input
									id="invite_code"
									value={formData.invite_code}
									onChange={(e) =>
										setFormData({ ...formData, invite_code: e.target.value })
									}
									required
									placeholder="Enter your invite code"
								/>
								<p className="text-xs text-muted-foreground">
									Contact an existing admin for an invite code.
								</p>
							</div>
						)}
						<div className="space-y-2">
							<Label htmlFor="institutional_id">{idLabel}</Label>
							<Input
								id="institutional_id"
								value={formData.institutional_id}
								onChange={(e) =>
									setFormData({
										...formData,
										institutional_id: e.target.value,
									})
								}
								required
							/>
						</div>
						{formData.role === "supervisor" && (
							<div className="space-y-2">
								<Label htmlFor="department_id">
									Department{" "}
									<span className="text-muted-foreground">(optional)</span>
								</Label>
								<select
									id="department_id"
									className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm"
									value={formData.department_id}
									onChange={(e) =>
										setFormData({ ...formData, department_id: e.target.value })
									}
								>
									<option value="">Select a department</option>
									{departments.map((dept) => (
										<option key={dept.id} value={dept.id}>
											{dept.name}
										</option>
									))}
								</select>
							</div>
						)}
						<div className="space-y-2">
							<Label htmlFor="password">Password</Label>
							<Input
								id="password"
								type="password"
								value={formData.password}
								onChange={(e) =>
									setFormData({ ...formData, password: e.target.value })
								}
								minLength={8}
								required
							/>
						</div>
						<div className="space-y-2">
							<Label htmlFor="confirmPassword">Confirm Password</Label>
							<Input
								id="confirmPassword"
								type="password"
								value={formData.confirmPassword}
								onChange={(e) =>
									setFormData({ ...formData, confirmPassword: e.target.value })
								}
								required
							/>
						</div>
						<Button type="submit" className="w-full" disabled={isSubmitting}>
							{isSubmitting ? "Creating account..." : "Create account"}
						</Button>
						<p className="text-center text-sm text-muted-foreground">
							Already have an account?{" "}
							<Link
								to="/login"
								className="font-medium text-primary hover:underline"
							>
								Sign in
							</Link>
						</p>
					</form>
				</CardContent>
			</Card>
		</div>
	);
}
