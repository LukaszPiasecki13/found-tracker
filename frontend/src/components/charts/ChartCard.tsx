import React from 'react';
import { Card, CardContent, Typography, Box, Skeleton } from '@mui/material';

interface ChartCardProps {
  title: string;
  subtitle?: string;
  loading?: boolean;
  error?: string | null;
  height?: number;
  children: React.ReactNode;
}

const ChartCard: React.FC<ChartCardProps> = ({
  title,
  subtitle,
  loading = false,
  error = null,
  height = 300,
  children,
}) => {
  return (
    <Card sx={{ height: '100%' }}>
      <CardContent sx={{ pb: 1 }}>
        <Typography variant="subtitle1" fontWeight={600}>
          {title}
        </Typography>
        {subtitle && (
          <Typography variant="caption" color="text.secondary">
            {subtitle}
          </Typography>
        )}
      </CardContent>
      <Box sx={{ px: 2, pb: 2, height }}>
        {loading ? (
          <Skeleton variant="rectangular" width="100%" height="100%" sx={{ borderRadius: 1 }} />
        ) : error ? (
          <Box
            display="flex"
            alignItems="center"
            justifyContent="center"
            height="100%"
            color="text.secondary"
          >
            <Typography variant="body2">{error}</Typography>
          </Box>
        ) : (
          children
        )}
      </Box>
    </Card>
  );
};

export default ChartCard;
