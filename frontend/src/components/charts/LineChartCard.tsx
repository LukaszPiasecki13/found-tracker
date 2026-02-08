import React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import ChartCard from './ChartCard';

const DEFAULT_COLORS = [
  '#1976d2', '#9c27b0', '#2e7d32', '#ed6c02', '#d32f2f',
  '#0288d1', '#7b1fa2', '#388e3c', '#f57c00', '#c62828',
];

interface LineChartCardProps {
  title: string;
  subtitle?: string;
  data: Record<string, unknown>[];
  dataKeys: string[];
  colors?: string[];
  loading?: boolean;
  error?: string | null;
  height?: number;
  yAxisFormatter?: (value: number) => string;
  showReferenceLine?: boolean; // line at y=0
}

const LineChartCard: React.FC<LineChartCardProps> = ({
  title,
  subtitle,
  data,
  dataKeys,
  colors = DEFAULT_COLORS,
  loading = false,
  error = null,
  height = 300,
  yAxisFormatter,
  showReferenceLine = false,
}) => {
  const formatYAxis = yAxisFormatter || ((v: number) => {
    if (Math.abs(v) >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
    if (Math.abs(v) >= 1_000) return `${(v / 1_000).toFixed(1)}k`;
    return v.toFixed(0);
  });

  const tooltipFormatter = (value: number | undefined) => {
    return new Intl.NumberFormat('pl-PL', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value ?? 0);
  };

  return (
    <ChartCard title={title} subtitle={subtitle} loading={loading} error={error} height={height}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 11 }}
            tickFormatter={(v) => {
              if (!v) return '';
              const d = new Date(v);
              return `${d.getMonth() + 1}/${d.getFullYear().toString().slice(2)}`;
            }}
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fontSize: 11 }}
            tickFormatter={formatYAxis}
            width={60}
          />
          <Tooltip
            formatter={tooltipFormatter}
            labelFormatter={(label) => {
              if (!label) return '';
              return new Date(label).toLocaleDateString('pl-PL');
            }}
          />
          {dataKeys.length > 1 && <Legend />}
          {showReferenceLine && (
            <ReferenceLine y={0} stroke="#999" strokeDasharray="3 3" />
          )}
          {dataKeys.map((key, i) => (
            <Line
              key={key}
              type="monotone"
              dataKey={key}
              stroke={colors[i % colors.length]}
              strokeWidth={2}
              dot={false}
              name={key}
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </ChartCard>
  );
};

export default LineChartCard;
