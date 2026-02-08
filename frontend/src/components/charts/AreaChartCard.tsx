import React from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import ChartCard from './ChartCard';

// Extended color palette for many assets
const AREA_COLORS = [
  '#1976d2', '#9c27b0', '#2e7d32', '#ed6c02', '#d32f2f',
  '#0288d1', '#7b1fa2', '#388e3c', '#f57c00', '#c62828',
  '#00838f', '#6a1b9a', '#558b2f', '#e65100', '#ad1457',
  '#0277bd', '#4527a0', '#33691e', '#bf360c', '#880e4f',
];

interface AreaChartCardProps {
  title: string;
  subtitle?: string;
  data: Record<string, unknown>[];
  dataKeys: string[];
  colors?: string[];
  loading?: boolean;
  error?: string | null;
  height?: number;
  stacked?: boolean;
}

const AreaChartCard: React.FC<AreaChartCardProps> = ({
  title,
  subtitle,
  data,
  dataKeys,
  colors = AREA_COLORS,
  loading = false,
  error = null,
  height = 300,
  stacked = true,
}) => {
  const formatYAxis = (v: number) => {
    if (Math.abs(v) >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
    if (Math.abs(v) >= 1_000) return `${(v / 1_000).toFixed(1)}k`;
    return v.toFixed(0);
  };

  const tooltipFormatter = (value: number | undefined) => {
    return new Intl.NumberFormat('pl-PL', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value ?? 0);
  };

  return (
    <ChartCard title={title} subtitle={subtitle} loading={loading} error={error} height={height}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
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
          <Legend wrapperStyle={{ fontSize: 11 }} />
          {dataKeys.map((key, i) => (
            <Area
              key={key}
              type="monotone"
              dataKey={key}
              stackId={stacked ? '1' : undefined}
              stroke={colors[i % colors.length]}
              fill={colors[i % colors.length]}
              fillOpacity={0.6}
              name={key}
              isAnimationActive={false}
            />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    </ChartCard>
  );
};

export default AreaChartCard;
