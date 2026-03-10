// frontend/src/components/charts/ProgressTimeline.tsx

import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import type { ProgressDataPoint } from "@/types/dashboard";

interface ProgressTimelineProps {
  data: ProgressDataPoint[];
}

export default function ProgressTimeline({ data }: ProgressTimelineProps) {
  if (data.length === 0) {
    return <p className="text-sm text-muted-foreground py-8 text-center">No data yet</p>;
  }

  return (
    <ResponsiveContainer width="100%" height={250}>
      <LineChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 12 }}
          tickFormatter={(val) => {
            const d = new Date(String(val));
            return `${d.getMonth() + 1}/${d.getDate()}`;
          }}
        />
        <YAxis tick={{ fontSize: 12 }} />
        <Tooltip
          labelFormatter={(val) => val ? new Date(String(val)).toLocaleDateString() : ""}
          formatter={(value) => [value, "Total Cases"]}
        />
        <Line
          type="monotone"
          dataKey="cumulative_cases"
          stroke="#6366f1"
          strokeWidth={2}
          dot={{ r: 3 }}
          activeDot={{ r: 5 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
