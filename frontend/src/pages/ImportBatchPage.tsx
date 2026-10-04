import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  CircularProgress,
  Chip,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  Alert,
} from '@mui/material';
import { ArrowBack as ArrowBackIcon } from '@mui/icons-material';
import dayjs from 'dayjs';
import {
  useImportBatch,
  useRevertImportBatch,
} from '../hooks/useImports';
import { ImportRowsTable } from '../components/import/ImportRowsTable';
import { ReconciliationReportCard } from '../components/import/ReconciliationReportCard';
import type { ImportBatchStatus } from '../types/api';

const ImportBatchPage: React.FC = () => {
  const { portfolioId, batchId } = useParams<{
    portfolioId: string;
    batchId: string;
  }>();
  const navigate = useNavigate();
  const portfolioIdNum = portfolioId ? parseInt(portfolioId) : undefined;
  const batchIdNum = batchId ? parseInt(batchId) : undefined;

  const { data: batch, isLoading } = useImportBatch(
    portfolioIdNum,
    batchIdNum
  );
  const revertMutation = useRevertImportBatch();

  const [revertDialogOpen, setRevertDialogOpen] = useState(false);

  const handleRevertClick = () => {
    setRevertDialogOpen(true);
  };

  const handleRevertConfirm = () => {
    setRevertDialogOpen(false);
    if (!portfolioIdNum || !batchIdNum) return;
    revertMutation.mutate(
      { portfolioId: portfolioIdNum, batchId: batchIdNum },
      // The batch is deleted with its operations: back to the list.
      { onSuccess: () => navigate('/import') }
    );
  };

  const getStatusColor = (status: ImportBatchStatus) => {
    const colors: Record<ImportBatchStatus, 'success' | 'warning'> = {
      committed: 'success',
      reverted: 'warning',
    };
    return colors[status];
  };

  const getStatusLabel = (status: ImportBatchStatus) => {
    const labels: Record<ImportBatchStatus, string> = {
      committed: 'Zatwierdzone',
      reverted: 'Cofnięte',
    };
    return labels[status];
  };

  if (isLoading) {
    return (
      <Box display="flex" justifyContent="center" p={4}>
        <CircularProgress />
      </Box>
    );
  }

  if (!batch) {
    return (
      <Box>
        <Button
          startIcon={<ArrowBackIcon />}
          onClick={() => navigate(-1)}
          sx={{ mb: 2 }}
        >
          Wróć
        </Button>
        <Alert severity="error">Nie znaleziono paczki importu</Alert>
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
        <Button
          startIcon={<ArrowBackIcon />}
          onClick={() => navigate(-1)}
          sx={{ mr: 2 }}
        >
          Wróć
        </Button>
        <Typography variant="h4" component="h1" sx={{ flex: 1 }}>
          {batch.filename}
        </Typography>
        <Chip
          label={getStatusLabel(batch.status)}
          color={getStatusColor(batch.status)}
        />
      </Box>

      <Box sx={{ mb: 3 }}>
        <Typography variant="body2" color="text.secondary">
          Data importu: {dayjs(batch.created_at).format('DD.MM.YYYY HH:mm')}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Wierszy: {batch.rows.length}
        </Typography>
      </Box>

      <ReconciliationReportCard
        reconciliation={batch.reconciliation}
      />

      <ImportRowsTable rows={batch.rows} />

      <Box sx={{ display: 'flex', gap: 2 }}>
        {batch.status === 'committed' && (
          <Button
            variant="contained"
            color="warning"
            onClick={handleRevertClick}
            disabled={revertMutation.isPending}
          >
            {revertMutation.isPending ? (
              <CircularProgress size={24} />
            ) : (
              'Cofnij import'
            )}
          </Button>
        )}
      </Box>

      <Dialog open={revertDialogOpen} onClose={() => setRevertDialogOpen(false)}>
        <DialogTitle>Cofnij import</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Czy na pewno chcesz cofnąć ten import? Spowoduje to usunięcie
            wszystkich dodanych operacji.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRevertDialogOpen(false)}>
            Anuluj
          </Button>
          <Button onClick={handleRevertConfirm} color="warning">
            Cofnij
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default ImportBatchPage;

