import {
	AlertCircle,
	CheckCircle,
	ChevronDown,
	Lock,
	RefreshCw,
	X,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { departmentService } from "@/services/departments";
import { rotationService } from "@/services/rotations";
import type { Department } from "@/types/department";
import type { Rotation } from "@/types/rotation";

interface RotationSelectorProps {
	onRotationChange?: (departmentId: string | null) => void;
}

export default function RotationSelector({
	onRotationChange,
}: RotationSelectorProps) {
	const [currentRotation, setCurrentRotation] = useState<Rotation | null>(
		null,
	);
	const [departments, setDepartments] = useState<Department[]>([]);
	const [isLoading, setIsLoading] = useState(true);
	const [isChanging, setIsChanging] = useState(false);
	const [error, setError] = useState("");
	const [success, setSuccess] = useState("");

	// Selection state — separate from submission
	const [selectedDeptId, setSelectedDeptId] = useState<string>("");
	const [daysOffset, setDaysOffset] = useState(0);

	const onRotationChangeRef = useRef(onRotationChange);

	useEffect(() => {
		onRotationChangeRef.current = onRotationChange;
	}, [onRotationChange]);

	const fetchData = useCallback(async () => {
		try {
			setIsLoading(true);
			setError("");
			const [rotationData, deptsData] = await Promise.all([
				rotationService.getCurrent(),
				departmentService.list(),
			]);
			setCurrentRotation(rotationData);
			setDepartments(deptsData.filter((d) => d.is_active));
		} catch {
			setError("Failed to load rotation data");
		} finally {
			setIsLoading(false);
		}
	}, []);

	useEffect(() => {
		fetchData();
	}, [fetchData]);

	const isLocked = !!currentRotation;

	const handleConfirm = async () => {
		if (!selectedDeptId) return;

		try {
			setIsChanging(true);
			setError("");
			setSuccess("");
			const newRotation = await rotationService.set({
				department_id: selectedDeptId,
				days_offset: daysOffset,
			});
			setCurrentRotation(newRotation);
			setSelectedDeptId("");
			setDaysOffset(0);
			setSuccess("Rotation set successfully");
			onRotationChangeRef.current?.(selectedDeptId);
			setTimeout(() => setSuccess(""), 3000);
		} catch {
			setError("Failed to set rotation");
		} finally {
			setIsChanging(false);
		}
	};

	const handleCancel = () => {
		setSelectedDeptId("");
		setDaysOffset(0);
		setError("");
	};

	if (isLoading) {
		return (
			<div className="flex items-center gap-2 text-sm text-muted-foreground">
				<RefreshCw className="h-4 w-4 animate-spin" />
				<span>Loading rotation...</span>
			</div>
		);
	}

	const currentDept = departments.find(
		(d) => d.id === currentRotation?.department_id,
	);
	const selectedDept = departments.find((d) => d.id === selectedDeptId);

	return (
		<div className="space-y-3">
			<div className="flex items-center justify-between">
				<label className="text-sm font-medium">Current Rotation</label>
				{isLocked && (
					<span className="flex items-center gap-1 text-xs text-muted-foreground">
						<Lock className="h-3 w-3" />
						Locked
					</span>
				)}
			</div>

			{isLocked ? (
				<div className="flex items-center gap-2 rounded-md border border-input bg-muted/50 px-3 py-2 text-sm">
					<Lock className="h-4 w-4 shrink-0 text-muted-foreground" />
					<span className="font-medium">
						{currentDept?.name || "Assigned"}
					</span>
				</div>
			) : (
				<>
					<div className="relative">
						<select
							value={selectedDeptId}
							onChange={(e) => setSelectedDeptId(e.target.value)}
							disabled={isChanging || departments.length === 0}
							className="w-full appearance-none rounded-md border border-input bg-background px-3 py-2 pr-8 text-sm shadow-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary disabled:cursor-not-allowed disabled:opacity-50"
						>
							<option value="" disabled>
								Select your current department rotation
							</option>
							{departments.map((dept) => (
								<option key={dept.id} value={dept.id}>
									{dept.name}
								</option>
							))}
						</select>
						<ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
					</div>

					{selectedDeptId && (
						<div className="space-y-3 rounded-md border border-primary/20 bg-primary/5 p-3">
							<div className="flex items-center justify-between">
								<span className="text-sm font-medium">
									{selectedDept?.name}
								</span>
								<button
									type="button"
									onClick={handleCancel}
									disabled={isChanging}
									aria-label="Cancel"
									className="text-muted-foreground hover:text-foreground disabled:opacity-50"
								>
									<X className="h-4 w-4" />
								</button>
							</div>

							<div className="space-y-1.5">
								<label
									htmlFor="days-offset"
									className="text-xs text-muted-foreground"
								>
									What day are you on? (leave at 0 if starting fresh)
								</label>
								<input
									id="days-offset"
									type="number"
									min={0}
									value={daysOffset}
									onChange={(e) =>
										setDaysOffset(Math.max(0, parseInt(e.target.value) || 0))
									}
									disabled={isChanging}
									className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary disabled:cursor-not-allowed disabled:opacity-50"
									placeholder="0"
								/>
							</div>

							<button
								type="button"
								onClick={handleConfirm}
								disabled={isChanging}
								className="w-full rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
							>
								{isChanging ? "Setting..." : "Confirm"}
							</button>
						</div>
					)}
				</>
			)}

			{isLocked && (
				<p className="text-xs text-muted-foreground">
					Contact an administrator to change your department assignment.
				</p>
			)}

			{error && (
				<div className="flex items-center gap-2 rounded-md bg-destructive/10 p-2 text-sm text-destructive">
					<AlertCircle className="h-4 w-4" />
					<span>{error}</span>
				</div>
			)}

			{success && (
				<div className="flex items-center gap-2 rounded-md bg-green-500/10 p-2 text-sm text-green-600 dark:text-green-400">
					<CheckCircle className="h-4 w-4" />
					<span>{success}</span>
				</div>
			)}

			{departments.length === 0 && !isLoading && (
				<p className="text-xs text-muted-foreground">
					No active departments available. Contact an administrator.
				</p>
			)}
		</div>
	);
}
