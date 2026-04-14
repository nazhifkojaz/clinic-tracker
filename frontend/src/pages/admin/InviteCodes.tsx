import { Check, Copy, Loader2, Plus } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { inviteCodeService } from "@/services/inviteCodes";
import type { InviteCode } from "@/types/inviteCode";

export default function InviteCodes() {
	const [codes, setCodes] = useState<InviteCode[]>([]);
	const [isLoading, setIsLoading] = useState(false);
	const [isGenerating, setIsGenerating] = useState(false);
	const [copiedId, setCopiedId] = useState<string | null>(null);
	const copyTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

	useEffect(() => {
		return () => {
			if (copyTimeoutRef.current) clearTimeout(copyTimeoutRef.current);
		};
	}, []);

	const fetchCodes = async () => {
		try {
			setIsLoading(true);
			const data = await inviteCodeService.list();
			setCodes(data);
		} catch {
			toast.error("Failed to load invite codes");
		} finally {
			setIsLoading(false);
		}
	};

	useEffect(() => {
		fetchCodes();
	}, []);

	const handleGenerate = async () => {
		setIsGenerating(true);
		try {
			const newCode = await inviteCodeService.generate();
			setCodes((prev) => [newCode, ...prev]);
			toast.success("Invite code generated");
		} catch {
			toast.error("Failed to generate invite code");
		} finally {
			setIsGenerating(false);
		}
	};

	const handleCopy = async (code: string, id: string) => {
		try {
			await navigator.clipboard.writeText(code);
			if (copyTimeoutRef.current) clearTimeout(copyTimeoutRef.current);
			setCopiedId(id);
			copyTimeoutRef.current = setTimeout(() => setCopiedId(null), 2000);
		} catch {
			toast.error("Failed to copy code");
		}
	};

	const statusBadge = (status: InviteCode["status"]) => {
		if (status === "active") {
			return (
				<span className="rounded-full bg-green-100 px-2 py-1 text-xs font-medium text-green-700 dark:bg-green-900 dark:text-green-300">
					Active
				</span>
			);
		}
		return (
			<span className="rounded-full bg-gray-100 px-2 py-1 text-xs font-medium text-gray-600 dark:bg-gray-800 dark:text-gray-400">
				Used
			</span>
		);
	};

	return (
		<div className="space-y-6">
			<div className="flex items-center justify-between">
				<h1 className="text-2xl font-bold">Invite Codes</h1>
				<Button onClick={handleGenerate} disabled={isGenerating}>
					{isGenerating ? (
						<>
							<Loader2 className="mr-2 h-4 w-4 animate-spin" />
							Generating...
						</>
					) : (
						<>
							<Plus className="mr-2 h-4 w-4" />
							Generate Code
						</>
					)}
				</Button>
			</div>

			<p className="text-sm text-muted-foreground">
				Generate one-time invite codes to allow new admins to register. Share the
				code with a trusted user — it can only be used once.
			</p>

			<Card>
				<CardHeader>
					<CardTitle>All Codes ({codes.length})</CardTitle>
				</CardHeader>
				<CardContent className="p-0">
					{isLoading ? (
						<div className="flex items-center justify-center py-12">
							<Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
						</div>
					) : codes.length === 0 ? (
						<div className="py-12 text-center text-sm text-muted-foreground">
							No invite codes yet. Click "Generate Code" to create one.
						</div>
					) : (
						<div className="overflow-x-auto">
							<table className="w-full min-w-[500px]">
								<thead>
									<tr className="border-b text-left text-sm text-muted-foreground">
										<th className="p-4">Code</th>
										<th className="p-4">Status</th>
										<th className="p-4">Created</th>
										<th className="p-4">Used</th>
										<th className="p-4">Actions</th>
									</tr>
								</thead>
								<tbody>
									{codes.map((code) => (
										<tr key={code.id} className="border-b last:border-0">
											<td className="p-4">
												<code className="rounded bg-muted px-2 py-1 text-sm font-mono">
													{code.code}
												</code>
											</td>
											<td className="p-4">{statusBadge(code.status)}</td>
											<td className="p-4 text-sm text-muted-foreground">
												{new Date(code.created_at).toLocaleDateString()}
											</td>
											<td className="p-4 text-sm text-muted-foreground">
												{code.used_at
													? new Date(code.used_at).toLocaleDateString()
													: "—"}
											</td>
											<td className="p-4">
												{code.status === "active" && (
													<Button
														variant="ghost"
														size="icon-sm"
														onClick={() => handleCopy(code.code, code.id)}
														title="Copy code"
													>
														{copiedId === code.id ? (
															<Check className="h-4 w-4 text-green-600" />
														) : (
															<Copy className="h-4 w-4" />
														)}
													</Button>
												)}
											</td>
										</tr>
									))}
								</tbody>
							</table>
						</div>
					)}
				</CardContent>
			</Card>
		</div>
	);
}
