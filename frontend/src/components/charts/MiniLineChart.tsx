import React from 'react';
import { LineChart, Line, ResponsiveContainer, Tooltip } from 'recharts';

interface MiniLineChartProps {
  data: { value: number }[];
  color?: string;
  height?: number;
}

const MiniLineChart: React.FC<MiniLineChartProps> = ({
  data,
  color = '#1976d2',
  height = 50,
}) => {
  if (!data || data.length < 2) return null;

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data}>
        <Tooltip
          formatter={(value: number | undefined) =>
            new Intl.NumberFormat('pl-PL', {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            }).format(value ?? 0)
          }
          labelFormatter={() => ''}
          contentStyle={{ fontSize: 11, padding: '2px 6px' }}
        />
        <Line
          type="monotone"
          dataKey="value"
          stroke={color}
          strokeWidth={1.5}
          dot={false}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
};

export default MiniLineChart;
