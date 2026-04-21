import { FileText, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuthStore } from "@/stores/authStore";
import { userService } from "@/services/users";

const roleBadgeColor: Record<string, string> = {
	admin: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
	supervisor: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
	student: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
};

export default function Settings() {
	const { user } = useAuthStore();

	const [pwForm, setPwForm] = useState({
		current_password: "",
		new_password: "",
		confirm_password: "",
	});
	const [pwError, setPwError] = useState("");
	const [isChangingPw, setIsChangingPw] = useState(false);

	const [pendingChangesCount, setPendingChangesCount] = useState(0);

	useEffect(() => {
		if (user?.role !== "admin") {
			userService
				.getMyPendingChanges()
				.then((changes) => setPendingChangesCount(changes.length))
				.catch(() => {});
		}
	}, [user?.role]);

	const handleChangePassword = async (e: React.FormEvent) => {
		e.preventDefault();
		setPwError("");

		if (pwForm.new_password.length < 8) {
			setPwError("New password must be at least 8 characters");
			return;
		}
		if (pwForm.new_password !== pwForm.confirm_password) {
			setPwError("Passwords do not match");
			return;
		}

		setIsChangingPw(true);
		try {
			await userService.changePassword({
				current_password: pwForm.current_password,
				new_password: pwForm.new_password,
			});
			toast.success("Password changed successfully");
			setPwForm({
				current_password: "",
				new_password: "",
				confirm_password: "",
			});
		} catch (err: unknown) {
			const detail =
				(err as { response?: { data?: { detail?: string } } })?.response?.data
					?.detail || "Failed to change password";
			setPwError(detail);
		} finally {
			setIsChangingPw(false);
		}
	};

	if (!user) return null;

	return (
		<div className="space-y-6">
			<h1 className="text-2xl font-bold">Settings</h1>

			{/* Pending Changes Banner */}
			{user.role !== "admin" && pendingChangesCount > 0 && (
				<Card className="border-blue-200 bg-blue-50 dark:border-blue-900 dark:bg-blue-950">
					<CardContent className="flex items-center justify-between p-4">
						<div className="flex items-center gap-3">
							<FileText className="h-5 w-5 text-blue-600 dark:text-blue-400" />
							<div>
								<p className="font-medium text-blue-900 dark:text-blue-100">
									You have {pendingChangesCount} pending change
									{pendingChangesCount !== 1 ? "s" : ""}
								</p>
							</div>
						</div>
						<Button
							render={<Link to="/my-requests" />}
							nativeButton={false}
							variant="outline"
							className="border-blue-300 text-blue-700 hover:bg-blue-100 dark:border-blue-800 dark:text-blue-300 dark:hover:bg-blue-900"
						>
							View Requests
						</Button>
					</CardContent>
				</Card>
			)}

			{/* Account Information */}
			<Card>
				<CardHeader>
					<CardTitle>Account Information</CardTitle>
				</CardHeader>
				<CardContent>
					<div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
						<div>
							<span className="text-sm text-muted-foreground">Email</span>
							<p className="font-medium">{user.email}</p>
						</div>
						<div>
							<span className="text-sm text-muted-foreground">Role</span>
							<p>
								<span
									className={`inline-block rounded-full px-2 py-1 text-xs font-medium capitalize ${roleBadgeColor[user.role]}`}
								>
									{user.role}
								</span>
							</p>
						</div>
						<div>
							<span className="text-sm text-muted-foreground">
								{user.role === "student" ? "Student ID" : "Staff ID"}
							</span>
							<p className="font-medium">{user.institutional_id || "—"}</p>
						</div>
						<div>
							<span className="text-sm text-muted-foreground">Registered</span>
							<p className="font-medium">
								{new Date(user.created_at).toLocaleDateString()}
							</p>
						</div>
					</div>
				</CardContent>
			</Card>

			{/* Change Password */}
			<Card>
				<CardHeader>
					<CardTitle>Change Password</CardTitle>
				</CardHeader>
				<CardContent>
					<form onSubmit={handleChangePassword} className="space-y-4">
						{pwError && (
							<div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
								{pwError}
							</div>
						)}
						<div className="space-y-2">
							<Label htmlFor="current_password">Current Password</Label>
							<Input
								id="current_password"
								type="password"
								value={pwForm.current_password}
								onChange={(e) =>
									setPwForm({ ...pwForm, current_password: e.target.value })
								}
								required
							/>
						</div>
						<div className="space-y-2">
							<Label htmlFor="new_password">New Password</Label>
							<Input
								id="new_password"
								type="password"
								value={pwForm.new_password}
								onChange={(e) =>
									setPwForm({ ...pwForm, new_password: e.target.value })
								}
								required
								minLength={8}
							/>
						</div>
						<div className="space-y-2">
							<Label htmlFor="confirm_password">Confirm New Password</Label>
							<Input
								id="confirm_password"
								type="password"
								value={pwForm.confirm_password}
								onChange={(e) =>
									setPwForm({ ...pwForm, confirm_password: e.target.value })
								}
								required
								minLength={8}
							/>
						</div>
						<div className="flex justify-end">
							<Button type="submit" disabled={isChangingPw}>
								{isChangingPw ? (
									<>
										<Loader2 className="mr-2 h-4 w-4 animate-spin" />
										Changing...
									</>
								) : (
									"Change Password"
								)}
							</Button>
						</div>
					</form>
				</CardContent>
			</Card>
		</div>
	);
}
