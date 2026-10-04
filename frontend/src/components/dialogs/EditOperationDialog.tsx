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
  Typography,
} from '@mui/material';
import dayjs from 'dayjs';
import { useUpdateOperation } from '../../hooks/useOperations';
import { getOperationTypeLabel } from '../../lib/operations';
import type { Operation, UpdateOperationRequest } from '../../types/api';

interface EditOperationDialogProps {
  operation: Operation;
  onClose: () => void;
}

interface OperationForm {
  quantity: string;
  price: string;
  amount: string;
  fee: string;
  fxRate: string;
  operationDate: string;
  notes: string;
}

// Which fields the ledger reads for each type (see `OperationValidator` in the backend domain).
const TRADE_TYPES = ['buy', 'sell'];
const AMOUNT_TYPES = ['deposit', 'withdrawal', 'dividend', 'interest', 'fee'];
const FX_TYPES = ['buy', 'sell', 'dividend'];

const toForm = (operation: Operation): OperationForm => ({
  quantity: operation.quantity != null ? String(operation.quantity) : '',
  price: operation.price != null ? String(operation.price) : '',
  amount: String(operation.amount),
  fee: String(operation.fee),
  fxRate: String(operation.fx_rate),
  operationDate: dayjs(operation.operation_date).format('YYYY-MM-DD'),
  notes: operation.notes ?? '',
});

const isPositive = (value: string) => value !== '' && Number(value) > 0;
const isNonNegative = (value: string) => value !== '' && Number(value) >= 0;

// Sends only the fields that differ from the stored operation (PATCH).
const buildChanges = (
  operation: Operation,
  form: OperationForm
): UpdateOperationRequest => {
  const changes: UpdateOperationRequest = {};
  const isTrade = TRADE_TYPES.includes(operation.operation_type);
  const hasAmount = AMOUNT_TYPES.includes(operation.operation_type);
  const hasFx = FX_TYPES.includes(operation.operation_type);

  if (isTrade && Number(form.quantity) !== operation.quantity) {
    changes.quantity = Number(form.quantity);
  }
  if (isTrade && Number(form.price) !== operation.price) {
    changes.price = Number(form.price);
  }
  if (hasAmount && Number(form.amount) !== operation.amount) {
    changes.amount = Number(form.amount);
  }
  if (Number(form.fee) !== operation.fee) {
    changes.fee = Number(form.fee);
  }
  if (hasFx && Number(form.fxRate) !== operation.fx_rate) {
    changes.fx_rate = Number(form.fxRate);
  }
  if (form.notes !== (operation.notes ?? '')) {
    changes.notes = form.notes;
  }
  if (form.operationDate !== dayjs(operation.operation_date).format('YYYY-MM-DD')) {
    changes.operation_date = form.operationDate;
  }
  return changes;
};

// Mounted only while open, so the form starts from the current operation on every opening.
const EditOperationDialog: React.FC<EditOperationDialogProps> = ({ operation, onClose }) => {
  const [form, setForm] = useState<OperationForm>(() => toForm(operation));
  const updateOperationMutation = useUpdateOperation();

  const isTrade = TRADE_TYPES.includes(operation.operation_type);
  const hasAmount = AMOUNT_TYPES.includes(operation.operation_type);
  const hasFx = FX_TYPES.includes(operation.operation_type);
  const isPending = updateOperationMutation.isPending;

  const isValid =
    form.operationDate !== '' &&
    isNonNegative(form.fee) &&
    (!isTrade || (isPositive(form.quantity) && isPositive(form.price))) &&
    (!hasAmount || isPositive(form.amount)) &&
    (!hasFx || isPositive(form.fxRate));

  const updateField =
    (field: keyof OperationForm) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm((prev) => ({ ...prev, [field]: e.target.value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!isValid) {
      return;
    }

    const changes = buildChanges(operation, form);
    if (Object.keys(changes).length === 0) {
      onClose();
      return;
    }

    try {
      await updateOperationMutation.mutateAsync({ id: operation.id, data: changes });
      onClose();
    } catch {
      // Error is handled by the mutation
    }
  };

  const numberProps = { type: 'number', required: true, fullWidth: true, disabled: isPending };

  return (
    <Dialog open onClose={onClose} maxWidth="sm" fullWidth>
      <form onSubmit={handleSubmit}>
        <DialogTitle>
          Edytuj operację
          <Typography variant="body2" color="text.secondary">
            {getOperationTypeLabel(operation.operation_type)}
            {operation.asset ? ` · ${operation.asset.ticker}` : ''}
          </Typography>
        </DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
            {isTrade && (
              <>
                <TextField
                  {...numberProps}
                  label="Ilość"
                  value={form.quantity}
                  onChange={updateField('quantity')}
                  inputProps={{ step: 'any', min: '0' }}
                />
                <TextField
                  {...numberProps}
                  label="Cena"
                  value={form.price}
                  onChange={updateField('price')}
                  inputProps={{ step: 'any', min: '0' }}
                />
              </>
            )}

            {hasAmount && (
              <TextField
                {...numberProps}
                label="Kwota"
                value={form.amount}
                onChange={updateField('amount')}
                inputProps={{ step: '0.01', min: '0' }}
              />
            )}

            <TextField
              {...numberProps}
              label="Prowizja"
              value={form.fee}
              onChange={updateField('fee')}
              inputProps={{ step: '0.01', min: '0' }}
            />

            {hasFx && (
              <TextField
                {...numberProps}
                label="Kurs wymiany"
                value={form.fxRate}
                onChange={updateField('fxRate')}
                inputProps={{ step: 'any', min: '0' }}
                helperText="Kurs waluty waloru wobec waluty portfela"
              />
            )}

            <TextField
              label="Data operacji"
              type="date"
              value={form.operationDate}
              onChange={updateField('operationDate')}
              required
              fullWidth
              disabled={isPending}
              InputLabelProps={{ shrink: true }}
            />

            <TextField
              label="Notatki"
              value={form.notes}
              onChange={updateField('notes')}
              multiline
              rows={3}
              fullWidth
              disabled={isPending}
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose} disabled={isPending}>
            Anuluj
          </Button>
          <Button type="submit" variant="contained" disabled={isPending || !isValid}>
            {isPending ? <CircularProgress size={24} /> : 'Zapisz'}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
};

export default EditOperationDialog;
