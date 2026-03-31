import {
	AlertTriangle,
	ChevronDown,
	ChevronUp,
	Clock,
	Loader2,
	AlertCircle,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import RotationSelector from "@/components/RotationSelector";
import { dashboardService } from "@/services/dashboard";
import type {
	DepartmentTrackerEntry,
	DepartmentTrackerData,
	CaseStatusColor,
} from "@/types/dashboard";

const COLOR_CLASSES: Record<
	CaseStatusColor,
	{ bar: string; badge: string; text: string }
> = {
	red: {
		bar: "bg-red-500",
		badge: "bg-red-100 text-red-700",
		text: "text-red-700",
	},
	yellow: {
		bar: "bg-yellow-500",
		badge: "bg-yellow-100 text-yellow-700",
		text: "text-yellow-700",
	},
	green: {
		bar: "bg-green-500",
		badge: "bg-green-100 text-green-700",
		text: "text-green-700",
	},
};

function TrackerCard({
	entry,
	prominent = false,
}: {
	entry: DepartmentTrackerEntry;
	prominent?: boolean;
}) {
	const colors = COLOR_CLASSES[entry.case_status_color];

	return (
		<Card className={prominent ? "border-primary border-2" : ""}>
			<CardHeader className="pb-2">
				<div className="flex items-center justify-between">
					<CardTitle
						className={prominent ? "text-lg" : "text-sm font-medium"}
					>
						{entry.department_name}
					</CardTitle>
					{entry.is_current && (
						<span className="text-xs bg-primary/10 text-primary px-2 py-0.5 rounded-full font-medium">
							Current
						</span>
					)}
				</div>
			</CardHeader>
			<CardContent className="space-y-3">
				{/* Time progress */}
				<div>
					<div className="flex justify-between text-sm mb-1">
						<span className="text-muted-foreground">Time</span>
						<span className="font-medium">
							Day {entry.days_active} of {entry.rotation_duration_days}
						</span>
					</div>
					<div className="h-2 rounded-full bg-secondary">
						<div
							className="h-2 rounded-full bg-primary transition-all"
							style={{
								width: `${Math.min(entry.time_completion_percentage, 100)}%`,
							}}
						/>
					</div>
				</div>

				{/* Case progress */}
				<div>
					<div className="flex justify-between text-sm mb-1">
						<span className="text-muted-foreground">Cases</span>
						<span className={`font-medium ${colors.text}`}>
							{entry.total_completed}/{entry.total_required} (
							{entry.case_completion_percentage.toFixed(0)}%)
						</span>
					</div>
					<div className="h-2 rounded-full bg-secondary">
						<div
							className={`h-2 rounded-full transition-all ${colors.bar}`}
							style={{
								width: `${Math.min(entry.case_completion_percentage, 100)}%`,
							}}
						/>
					</div>
					{entry.total_pending > 0 && (
						<p className="text-xs text-muted-foreground mt-1">
							+{entry.total_pending} pending approval
						</p>
					)}
				</div>
			</CardContent>
		</Card>
	);
}

export default function RotationTracker() {
	const [data, setData] = useState<DepartmentTrackerData | null>(null);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState("");
	const [showAll, setShowAll] = useState(false);

	const loadTracker = useCallback(async () => {
		try {
			setLoading(true);
			setError("");
			const result = await dashboardService.getRotationTracker();
			setData(result);
		} catch {
			setError("Failed to load rotation tracker data");
		} finally {
			setLoading(false);
		}
	}, []);

	const handleRotationChange = useCallback(() => {
		loadTracker();
	}, [loadTracker]);

	useEffect(() => {
		loadTracker();
	}, [loadTracker]);

	if (loading) {
		return (
			<div className="flex items-center justify-center gap-2 py-20">
				<Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
				<span className="text-muted-foreground">Loading tracker...</span>
			</div>
		);
	}

	if (error || !data) {
		return (
			<div className="flex items-center justify-center gap-2 py-20 text-destructive">
				<AlertCircle className="h-5 w-5" />
				<span>{error || "No data available"}</span>
			</div>
		);
	}

	const currentEntry = data.entries.find((e) => e.is_current);
	const otherEntries = data.entries.filter((e) => !e.is_current);

	return (
		<div className="space-y-6">
			<div className="flex items-center justify-between">
				<h1 className="text-2xl font-bold">Department Tracker</h1>
				<div className="flex items-center gap-2 text-sm text-muted-foreground">
					<Clock className="h-4 w-4" />
					<span>Rotation Progress</span>
				</div>
			</div>


			{/* Rotation selector */}
			<Card>
				<CardContent className="pt-4">
					<RotationSelector onRotationChange={handleRotationChange} />
				</CardContent>
			</Card>

			{/* Unassigned warning */}
			{!data.current_department_id && (
				<div className="flex items-center gap-3 rounded-lg border border-yellow-300 bg-yellow-50 px-4 py-3 text-yellow-800">
					<AlertTriangle className="h-5 w-5 shrink-0" />
					<div className="text-sm">
						<p className="font-medium">No Department Assigned</p>
						<p className="mt-1">
							Select your current department rotation above to start
							tracking your progress.
						</p>
					</div>
				</div>
			)}
			{/* Warning banner */}
			{data.show_warning && (
				<div className="flex items-center gap-3 rounded-lg border border-yellow-300 bg-yellow-50 px-4 py-3 text-yellow-800">
					<AlertTriangle className="h-5 w-5 shrink-0" />
					<span className="text-sm font-medium">
						You are past the halfway point of your current rotation but
						below 60% case completion. Review your submissions and catch up
						before the rotation ends.
					</span>
				</div>
			)}

			{/* Current rotation */}
			{currentEntry && (
				<div className="space-y-2">
					<h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
						Current Rotation
					</h2>
					<TrackerCard entry={currentEntry} prominent />
				</div>
			)}

			{/* All departments toggle */}
			{otherEntries.length > 0 && (
				<div className="space-y-3">
					<Button
						variant="outline"
						size="sm"
						onClick={() => setShowAll(!showAll)}
						className="w-full"
					>
						{showAll ? (
							<>
								<ChevronUp className="mr-2 h-4 w-4" />
								Hide other departments
							</>
						) : (
							<>
								<ChevronDown className="mr-2 h-4 w-4" />
								View all departments ({otherEntries.length})
							</>
						)}
					</Button>

					{showAll && (
						<div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
							{otherEntries.map((entry) => (
								<TrackerCard key={entry.department_id} entry={entry} />
							))}
						</div>
					)}
				</div>
			)}

			{!currentEntry && otherEntries.length === 0 && (
				<Card>
					<CardContent className="py-10 text-center text-muted-foreground">
						No rotation data available yet. Set your current department to
						start tracking.
					</CardContent>
				</Card>
			)}
		</div>
	);
}
