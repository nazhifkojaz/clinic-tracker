
import { useMemo } from "react";
import {
	Bar,
	BarChart,
	CartesianGrid,
	Cell,
	ResponsiveContainer,
	Tooltip,
	XAxis,
	YAxis,
} from "recharts";
import {
	useMutedColor,
	useSuccessColor,
	useWarningColor,
} from "@/hooks/useThemeColor";

interface StudentDistributionProps {
	onTrack: number;
	atRisk: number;
	unassigned: number;
}

export default function StudentDistribution({
	onTrack,
	atRisk,
	unassigned,
}: StudentDistributionProps) {
	const successColor = useSuccessColor();
	const warningColor = useWarningColor();
	const mutedColor = useMutedColor();

	const COLORS = useMemo(
		() => ({
			"On Track": successColor,
			"At Risk": warningColor,
			Unassigned: mutedColor,
		}),
		[successColor, warningColor, mutedColor],
	);

	const data = useMemo(
		() => [
			{ name: "On Track", count: onTrack },
			{ name: "At Risk", count: atRisk },
			{ name: "Unassigned", count: unassigned },
		],
		[onTrack, atRisk, unassigned],
	);

	return (
		<ResponsiveContainer width="100%" height={200}>
			<BarChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
				<CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
				<XAxis dataKey="name" tick={{ fontSize: 12 }} />
				<YAxis tick={{ fontSize: 12 }} allowDecimals={false} />
				<Tooltip />
				<Bar dataKey="count" radius={[4, 4, 0, 0]} barSize={48}>
					{data.map((entry) => (
						<Cell
							key={entry.name}
							fill={COLORS[entry.name as keyof typeof COLORS]}
						/>
					))}
				</Bar>
			</BarChart>
		</ResponsiveContainer>
	);
}
