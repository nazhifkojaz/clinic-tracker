// frontend/src/components/charts/StudentDistribution.tsx

import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from "recharts";

interface StudentDistributionProps {
  onTrack: number;
  atRisk: number;
  behind: number;
}

const COLORS = { "On Track": "#22c55e", "At Risk": "#f59e0b", "Behind": "#ef4444" };

export default function StudentDistribution({ onTrack, atRisk, behind }: StudentDistributionProps) {
  const data = [
    { name: "On Track", count: onTrack },
    { name: "At Risk", count: atRisk },
    { name: "Behind", count: behind },
  ];

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
        <XAxis dataKey="name" tick={{ fontSize: 12 }} />
        <YAxis tick={{ fontSize: 12 }} allowDecimals={false} />
        <Tooltip />
        <Bar dataKey="count" radius={[4, 4, 0, 0]} barSize={48}>
          {data.map((entry) => (
            <Cell key={entry.name} fill={COLORS[entry.name as keyof typeof COLORS]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
