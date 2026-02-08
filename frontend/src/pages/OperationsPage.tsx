import React from 'react';
import { Box, Typography } from '@mui/material';
import { useOperations } from '../hooks/useOperations';
import OperationsTable from '../components/OperationsTable';

const OperationsPage: React.FC = () => {
  const { data: operations, isLoading } = useOperations();

  return (
    <Box>
      <Typography variant="h4" component="h1" gutterBottom>
        Wszystkie operacje
      </Typography>

      <Typography variant="body2" color="text.secondary" gutterBottom sx={{ mb: 3 }}>
        Historia transakcji ze wszystkich portfeli
      </Typography>

      <OperationsTable operations={operations || []} isLoading={isLoading} showPocket={true} />
    </Box>
  );
};

export default OperationsPage;
