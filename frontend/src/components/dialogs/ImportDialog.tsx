import React, { useState } from 'react';
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Divider,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import { CloudUpload as CloudUploadIcon } from '@mui/icons-material';
import dayjs from 'dayjs';
import {
  useCommitImport,
  useImports,
  usePreviewImport,
  useRevertImportBatch,
} from '../../hooks/useImports';
import { getErrorMessage } from '../../lib/api';
import { ImportRowsTable } from '../import/ImportRowsTable';
import { ReconciliationReportCard } from '../import/ReconciliationReportCard';
import type { ImportBatchSummary, ImportPreview } from '../../types/api';

interface ImportDialogProps {
  open: boolean;
  onClose: () => void;
  pocketId: number;
}

const ImportDialog: React.FC<ImportDialogProps> = ({ open, onClose, pocketId }) => {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [revertTarget, setRevertTarget] = useState<ImportBatchSummary | null>(null);

  const { data: imports, isLoading: importsLoading } = useImports(open ? pocketId : undefined);
  const previewMutation = usePreviewImport();
  const commitMutation = useCommitImport();
  const revertMutation = useRevertImportBatch();

  const busy = previewMutation.isPending || commitMutation.isPending;

  const resetPreview = () => {
    setFile(null);
    setPreview(null);
    setFileError(null);
    previewMutation.reset();
  };

  const handleClose = () => {
    if (busy) return;
    resetPreview();
    onClose();
  };

  const handleFile = (selected: File) => {
    resetPreview();
    if (!selected.name.toLowerCase().endsWith('.xlsx')) {
      setFileError('Wybierz plik Excel (.xlsx).');
      return;
    }
    setFile(selected);
    previewMutation.mutate({ portfolioId: pocketId, file: selected }, { onSuccess: setPreview });
  };

  const handleDrag = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped && !busy) handleFile(dropped);
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.currentTarget.files?.[0];
    if (selected) handleFile(selected);
    // Allow choosing the same file again after cancelling.
    e.currentTarget.value = '';
  };

  const handleCommit = () => {
    if (!file) return;
    commitMutation.mutate(
      { portfolioId: pocketId, file },
      {
        onSuccess: () => {
          resetPreview();
          onClose();
        },
      }
    );
  };

  const handleRevert = () => {
    if (!revertTarget) return;
    revertMutation.mutate(
      { portfolioId: pocketId, batchId: revertTarget.id },
      { onSettled: () => setRevertTarget(null) }
    );
  };

  const hasBlockingRows =
    preview?.rows.some((row) => row.row_status === 'error' || row.row_status === 'unrecognized') ??
    false;
  const alreadyImported = preview !== null && preview.existing_batch_id !== null;
  const canCommit = preview !== null && !hasBlockingRows && !alreadyImported;

  return (
    <>
      <Dialog open={open} onClose={handleClose} maxWidth="lg" fullWidth>
        <DialogTitle>Import z pliku</DialogTitle>
        <DialogContent>
          <Paper
            variant="outlined"
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            sx={{
              p: 3,
              mb: 3,
              textAlign: 'center',
              border: '2px dashed',
              borderColor: dragActive ? 'primary.main' : 'divider',
              backgroundColor: dragActive ? 'action.hover' : 'background.paper',
              transition: 'all 0.2s ease',
            }}
          >
            <input
              type="file"
              accept=".xlsx"
              onChange={handleFileInput}
              style={{ display: 'none' }}
              id="import-file-input"
              disabled={busy}
            />
            <label htmlFor="import-file-input" style={{ cursor: busy ? 'default' : 'pointer', display: 'block' }}>
              <CloudUploadIcon sx={{ fontSize: 40, color: 'primary.main', mb: 1 }} />
              <Typography variant="h6" gutterBottom>
                {previewMutation.isPending
                  ? 'Generowanie podglądu...'
                  : file
                    ? file.name
                    : 'Przeciągnij plik Excel tutaj'}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                lub kliknij, aby wybrać plik (.xlsx, maksymalnie 10 MB)
              </Typography>
            </label>
          </Paper>

          {fileError && (
            <Alert severity="error" sx={{ mb: 3 }}>
              {fileError}
            </Alert>
          )}

          {previewMutation.isError && (
            <Alert severity="error" sx={{ mb: 3 }}>
              {getErrorMessage(previewMutation.error)}
            </Alert>
          )}

          {preview && (
            <Box sx={{ mb: 3 }}>
              <Alert severity="info" sx={{ mb: 2 }}>
                Podgląd nie jest zapisywany — dane trafią do systemu dopiero po zatwierdzeniu.
              </Alert>

              {alreadyImported && (
                <Alert severity="warning" sx={{ mb: 2 }}>
                  Ten plik został już zatwierdzony. Cofnij ten import na liście poniżej, aby
                  wczytać go ponownie.
                </Alert>
              )}

              {hasBlockingRows && (
                <Alert severity="warning" sx={{ mb: 2 }}>
                  Plik zawiera wiersze z błędami lub nierozpoznane — nie można go zatwierdzić.
                </Alert>
              )}

              <ReconciliationReportCard reconciliation={preview.reconciliation} />
              <ImportRowsTable rows={preview.rows} />
            </Box>
          )}

          <Divider sx={{ mb: 2 }} />
          <Typography variant="subtitle1" gutterBottom>
            Zatwierdzone importy
          </Typography>

          {importsLoading ? (
            <Box display="flex" justifyContent="center" p={2}>
              <CircularProgress size={24} />
            </Box>
          ) : imports && imports.length > 0 ? (
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Plik</TableCell>
                    <TableCell>Data</TableCell>
                    <TableCell align="right">Akcje</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {imports.map((batch) => (
                    <TableRow key={batch.id} hover>
                      <TableCell>{batch.filename}</TableCell>
                      <TableCell>{dayjs(batch.created_at).format('DD.MM.YYYY HH:mm')}</TableCell>
                      <TableCell align="right">
                        <Button
                          size="small"
                          color="warning"
                          onClick={() => setRevertTarget(batch)}
                          disabled={busy || revertMutation.isPending}
                        >
                          Cofnij
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          ) : (
            <Typography variant="body2" color="text.secondary">
              Brak importów w tym portfelu.
            </Typography>
          )}
        </DialogContent>
        <DialogActions>
          {preview && (
            <Button onClick={resetPreview} disabled={busy}>
              Anuluj
            </Button>
          )}
          <Button onClick={handleClose} disabled={busy}>
            Zamknij
          </Button>
          {preview && (
            <Button variant="contained" onClick={handleCommit} disabled={!canCommit || busy}>
              {commitMutation.isPending ? 'Zatwierdzanie...' : 'Zatwierdź import'}
            </Button>
          )}
        </DialogActions>
      </Dialog>

      <Dialog open={revertTarget !== null} onClose={() => setRevertTarget(null)}>
        <DialogTitle>Cofnij import</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Czy na pewno chcesz cofnąć import „{revertTarget?.filename}”? Spowoduje to usunięcie
            wszystkich operacji z tego pliku.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRevertTarget(null)} disabled={revertMutation.isPending}>
            Anuluj
          </Button>
          <Button onClick={handleRevert} color="warning" disabled={revertMutation.isPending}>
            {revertMutation.isPending ? <CircularProgress size={20} /> : 'Cofnij'}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
};

export default ImportDialog;
