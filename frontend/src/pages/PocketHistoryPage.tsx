import React from 'react';
import { useParams } from 'react-router-dom';
import { Box, Typography, CircularProgress } from '@mui/material';
import { useOperations } from '../hooks/useOperations';
import OperationsTable from '../components/OperationsTable';

const PocketHistoryPage: React.FC = () => {
  const { slug } = useParams<{ slug: string }>();
  const pocketName = decodeURIComponent(slug || '');

  const { data: operations, isLoading } = useOperations(pocketName);

  if (isLoading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="60vh">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Typography variant="h4" component="h1" gutterBottom>
        Historia operacji - {pocketName}
      </Typography>

      <Typography variant="body2" color="text.secondary" gutterBottom sx={{ mb: 3 }}>
        Wszystkie transakcje dla tego portfela
      </Typography>

      <OperationsTable operations={operations || []} isLoading={isLoading} showPocket={false} />
    </Box>
  );
};

export default PocketHistoryPage;
