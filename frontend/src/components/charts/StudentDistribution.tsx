// frontend/src/components/charts/StudentDistribution.tsx

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
	useDestructiveColor,
	useSuccessColor,
	useWarningColor,
} from "@/hooks/useThemeColor";

interface StudentDistributionProps {
	onTrack: number;
	atRisk: number;
	behind: number;
}

export default function StudentDistribution({
	onTrack,
	atRisk,
	behind,
}: StudentDistributionProps) {
	const successColor = useSuccessColor();
	const warningColor = useWarningColor();
	const destructiveColor = useDestructiveColor();

	const COLORS = useMemo(
		() => ({
			"On Track": successColor,
			"At Risk": warningColor,
			Behind: destructiveColor,
		}),
		[successColor, warningColor, destructiveColor],
	);

	const data = useMemo(
		() => [
			{ name: "On Track", count: onTrack },
			{ name: "At Risk", count: atRisk },
			{ name: "Behind", count: behind },
		],
		[onTrack, atRisk, behind],
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
