// frontend/src/components/charts/ProgressGauge.tsx

import { RadialBarChart, RadialBar, PolarAngleAxis } from "recharts";

interface ProgressGaugeProps {
  percentage: number;
  size?: number;
}

export default function ProgressGauge({ percentage, size = 180 }: ProgressGaugeProps) {
  const data = [{ value: percentage, fill: percentage >= 60 ? "#22c55e" : percentage >= 30 ? "#f59e0b" : "#ef4444" }];

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
        <PolarAngleAxis type="number" domain={[0, 100]} angleAxisId={0} tick={false} />
        <RadialBar dataKey="value" cornerRadius={6} background={{ fill: "#e5e7eb" }} />
      </RadialBarChart>
      <div className="-mt-[calc(50%+10px)] flex flex-col items-center">
        <span className="text-3xl font-bold">{percentage.toFixed(1)}%</span>
        <span className="text-sm text-muted-foreground">Overall</span>
      </div>
    </div>
  );
}
