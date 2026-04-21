
import { useMemo } from "react";
import { PolarAngleAxis, RadialBar, RadialBarChart } from "recharts";
import {
	useDestructiveColor,
	useMutedColor,
	useSuccessColor,
	useWarningColor,
} from "@/hooks/useThemeColor";

interface ProgressGaugeProps {
	percentage: number;
	size?: number;
}

export default function ProgressGauge({
	percentage,
	size = 180,
}: ProgressGaugeProps) {
	const successColor = useSuccessColor();
	const warningColor = useWarningColor();
	const destructiveColor = useDestructiveColor();
	const mutedColor = useMutedColor();

	const gaugeColor = useMemo(
		() =>
			percentage >= 60
				? successColor
				: percentage >= 30
					? warningColor
					: destructiveColor,
		[percentage, successColor, warningColor, destructiveColor],
	);

	const data = useMemo(
		() => [{ value: percentage, fill: gaugeColor }],
		[percentage, gaugeColor],
	);

	return (
		<div className="flex flex-col items-center">
			<RadialBarChart
				width={size}
				height={size}
				cx={size / 2}
				cy={size / 2}
				innerRadius={size * 0.35}
				outerRadius={size * 0.45}
				data={data}
				startAngle={90}
				endAngle={-270}
				barSize={12}
			>
				<PolarAngleAxis
					type="number"
					domain={[0, 100]}
					angleAxisId={0}
					tick={false}
				/>
				<RadialBar
					dataKey="value"
					cornerRadius={6}
					background={{ fill: mutedColor || "#e5e7eb" }}
				/>
			</RadialBarChart>
			<div className="-mt-[calc(50%+10px)] flex flex-col items-center">
				<span className="text-3xl font-bold">{percentage.toFixed(1)}%</span>
				<span className="text-sm text-muted-foreground">Overall</span>
			</div>
		</div>
	);
}
