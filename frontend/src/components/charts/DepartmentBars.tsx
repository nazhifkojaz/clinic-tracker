// frontend/src/components/charts/DepartmentBars.tsx

import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from "recharts";
import type { DepartmentProgress } from "@/types/dashboard";

interface DepartmentBarsProps {
  departments: DepartmentProgress[];
}

function getColor(pct: number): string {
  if (pct >= 60) return "#22c55e";
  if (pct >= 30) return "#f59e0b";
  return "#ef4444";
}

export default function DepartmentBars({ departments }: DepartmentBarsProps) {
  if (departments.length === 0) {
    return <p className="text-sm text-muted-foreground py-8 text-center">No departments</p>;
  }

  const data = departments.map((d) => ({
    name: d.department_name,
    completion: d.completion_percentage,
  }));

  return (
    <ResponsiveContainer width="100%" height={Math.max(200, departments.length * 50)}>
      <BarChart data={data} layout="vertical" margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
        <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 12 }} unit="%" />
        <YAxis type="category" dataKey="name" tick={{ fontSize: 12 }} width={120} />
        <Tooltip formatter={(value) => [`${Number(value).toFixed(1)}%`, "Completion"]} />
        <Bar dataKey="completion" radius={[0, 4, 4, 0]} barSize={24}>
          {data.map((entry, index) => (
            <Cell key={index} fill={getColor(entry.completion)} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
