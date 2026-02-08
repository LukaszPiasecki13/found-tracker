import React from 'react';
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import ChartCard from './ChartCard';

const PIE_COLORS = [
  '#1976d2', '#9c27b0', '#2e7d32', '#ed6c02', '#d32f2f',
  '#0288d1', '#7b1fa2', '#388e3c', '#f57c00', '#c62828',
  '#00838f', '#6a1b9a', '#558b2f', '#e65100', '#ad1457',
];

interface PieDataItem {
  name: string;
  value: number;
}

interface PieChartCardProps {
  title: string;
  subtitle?: string;
  data: PieDataItem[];
  colors?: string[];
  loading?: boolean;
  error?: string | null;
  height?: number;
}

const RADIAN = Math.PI / 180;
const renderCustomizedLabel = ({
  cx,
  cy,
  midAngle,
  innerRadius,
  outerRadius,
  percent,
}: {
  cx?: number;
  cy?: number;
  midAngle?: number;
  innerRadius?: number;
  outerRadius?: number;
  percent?: number;
}) => {
  if (!cx || !cy || !midAngle || !innerRadius || !outerRadius || !percent) return null;
  if (percent < 0.05) return null; // hide labels for tiny slices
  const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
  const x = cx + radius * Math.cos(-midAngle * RADIAN);
  const y = cy + radius * Math.sin(-midAngle * RADIAN);

  return (
    <text
      x={x}
      y={y}
      fill="white"
      textAnchor="middle"
      dominantBaseline="central"
      fontSize={12}
      fontWeight={600}
    >
      {`${(percent * 100).toFixed(0)}%`}
    </text>
  );
};

const PieChartCard: React.FC<PieChartCardProps> = ({
  title,
  subtitle,
  data,
  colors = PIE_COLORS,
  loading = false,
  error = null,
  height = 300,
}) => {
  const filteredData = data.filter((d) => d.value > 0);

  const tooltipFormatter = (value: number | undefined) => {
    return new Intl.NumberFormat('pl-PL', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value ?? 0);
  };

  return (
    <ChartCard title={title} subtitle={subtitle} loading={loading} error={error} height={height}>
      {filteredData.length === 0 ? (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#999' }}>
          Brak danych
        </div>
      ) : (
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={filteredData}
              cx="50%"
              cy="50%"
              labelLine={false}
              label={renderCustomizedLabel}
              outerRadius="80%"
              dataKey="value"
              isAnimationActive={false}
            >
              {filteredData.map((_entry, index) => (
                <Cell key={`cell-${index}`} fill={colors[index % colors.length]} />
              ))}
            </Pie>
            <Tooltip formatter={tooltipFormatter} />
            <Legend
              layout="vertical"
              verticalAlign="middle"
              align="right"
              wrapperStyle={{ fontSize: 12 }}
            />
          </PieChart>
        </ResponsiveContainer>
      )}
    </ChartCard>
  );
};

export default PieChartCard;
