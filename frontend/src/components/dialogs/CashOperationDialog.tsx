import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Box,
  CircularProgress,
  Tabs,
  Tab,
} from '@mui/material';
import dayjs from 'dayjs';
import { useCreateOperation } from '../../hooks/useOperations';

interface CashOperationDialogProps {
  open: boolean;
  onClose: () => void;
  pocketId: number;
}

const CashOperationDialog: React.FC<CashOperationDialogProps> = ({ open, onClose, pocketId }) => {
  const [tabValue, setTabValue] = useState(0);
  const [amount, setAmount] = useState('');
  const [operationDate, setOperationDate] = useState(dayjs().format('YYYY-MM-DD'));
  const [notes, setNotes] = useState('');
  const createOperationMutation = useCreateOperation();

  const operationType = tabValue === 0 ? 'deposit' : 'withdrawal';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!amount) return;

    try {
      await createOperationMutation.mutateAsync({
        pocket: pocketId,
        operation_type: operationType,
        amount: parseFloat(amount),
        fee: 0,
        operation_date: operationDate,
        notes,
      });
      handleClose();
    } catch (error) {
      // Error handled by mutation
    }
  };

  const handleClose = () => {
    setAmount('');
    setNotes('');
    setOperationDate(dayjs().format('YYYY-MM-DD'));
    setTabValue(0);
    onClose();
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <form onSubmit={handleSubmit}>
        <DialogTitle>Operacja gotówkowa</DialogTitle>
        <DialogContent>
          <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
            <Tabs value={tabValue} onChange={(_, newValue) => setTabValue(newValue)}>
              <Tab label="Wpłata" />
              <Tab label="Wypłata" />
            </Tabs>
          </Box>

          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
            <TextField
              label="Kwota"
              type="number"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              required
              fullWidth
              autoFocus
              disabled={createOperationMutation.isPending}
              inputProps={{ step: '0.01', min: '0' }}
            />

            <TextField
              label="Data operacji"
              type="date"
              value={operationDate}
              onChange={(e) => setOperationDate(e.target.value)}
              required
              fullWidth
              disabled={createOperationMutation.isPending}
              InputLabelProps={{ shrink: true }}
            />

            <TextField
              label="Notatki"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              multiline
              rows={3}
              fullWidth
              disabled={createOperationMutation.isPending}
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleClose} disabled={createOperationMutation.isPending}>
            Anuluj
          </Button>
          <Button
            type="submit"
            variant="contained"
            disabled={createOperationMutation.isPending || !amount}
          >
            {createOperationMutation.isPending ? (
              <CircularProgress size={24} />
            ) : tabValue === 0 ? (
              'Wpłać'
            ) : (
              'Wypłać'
            )}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
};

export default CashOperationDialog;
