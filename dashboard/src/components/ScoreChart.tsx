import { ResponsiveContainer, BarChart, XAxis, YAxis, Tooltip, Bar, Cell } from 'recharts';

interface Props {
  contributions: Record<string, number>;
}

const COLORS = ['#818cf8', '#a855f7', '#38bdf8', '#f97316', '#22c55e', '#ec4899', '#facc15', '#60a5fa'];

function formatLabel(label: string): string {
  return label.replace(/([A-Z])/g, ' $1').trim();
}

export function ScoreChart({ contributions }: Props) {
  const entries = Object.entries(contributions);
  const data = entries.map(([metric, value]) => ({
    metric: formatLabel(metric),
    contribution: Number((value * 100).toFixed(2)),
  }));

  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={data} layout="vertical" margin={{ top: 16, right: 16, bottom: 16, left: 16 }}>
        <XAxis type="number" domain={[0, 'dataMax']} hide />
        <YAxis type="category" dataKey="metric" width={160} tick={{ fill: '#cbd5f5', fontSize: 12 }} />
        <Tooltip
          formatter={(value: number) => `${value.toFixed(2)} pts`}
          contentStyle={{ backgroundColor: '#10142a', border: '1px solid #475569', color: '#e2e8f0' }}
        />
        <Bar dataKey="contribution" radius={6}>
          {data.map((entry, index) => (
            <Cell key={entry.metric} fill={COLORS[index % COLORS.length]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
