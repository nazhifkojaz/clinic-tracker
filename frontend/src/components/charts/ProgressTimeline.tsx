// frontend/src/components/charts/ProgressTimeline.tsx

import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import type { ProgressDataPoint } from "@/types/dashboard";
import { usePrimaryColor } from "@/hooks/useThemeColor";

interface ProgressTimelineProps {
  data: ProgressDataPoint[];
}

// Module-level formatters (avoid re-creation on each render)
function formatTickLabel(val: unknown): string {
  const d = new Date(String(val));
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

function formatTooltipLabel(val: unknown): string {
  return val ? new Date(String(val)).toLocaleDateString() : "";
}

// Recharts formatter - use any to work around strict typing
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const formatValue = (value: any): [any, string] => [value, "Total Cases"];

export default function ProgressTimeline({ data }: ProgressTimelineProps) {
  const primaryColor = usePrimaryColor();

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
          tickFormatter={formatTickLabel}
        />
        <YAxis tick={{ fontSize: 12 }} />
        <Tooltip
          labelFormatter={formatTooltipLabel}
          formatter={formatValue}
        />
        <Line
          type="monotone"
          dataKey="cumulative_cases"
          stroke={primaryColor || "#6366f1"}
          strokeWidth={2}
          dot={{ r: 3 }}
          activeDot={{ r: 5 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
