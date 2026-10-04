import React, { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Paper,
  CircularProgress,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  Button,
  Alert,
  Link as MuiLink,
  type SelectChangeEvent,
} from '@mui/material';
import { CloudUpload as CloudUploadIcon } from '@mui/icons-material';
import dayjs from 'dayjs';
import { usePockets } from '../hooks/usePockets';
import {
  useImports,
  usePreviewImport,
  useCommitImport,
} from '../hooks/useImports';
import { ImportRowsTable } from '../components/import/ImportRowsTable';
import { ReconciliationReportCard } from '../components/import/ReconciliationReportCard';
import type { ImportBatchStatus, ImportPreview } from '../types/api';

const ImportPage: React.FC = () => {
  const navigate = useNavigate();
  const { data: pockets, isLoading: pocketsLoading } = usePockets();
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<number | ''>(
    ''
  );
  const [currentFile, setCurrentFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);

  const { data: imports, isLoading: importsLoading } = useImports(
    selectedPortfolioId ? (selectedPortfolioId as number) : undefined
  );
  const previewMutation = usePreviewImport();
  const commitMutation = useCommitImport();
  const [dragActive, setDragActive] = useState(false);

  const handlePortfolioChange = useCallback(
    (e: SelectChangeEvent<number | ''>) => {
      setSelectedPortfolioId(e.target.value as number | '');
      setCurrentFile(null);
      setPreview(null);
    },
    []
  );

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

    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      handleFile(files[0]);
    }
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.currentTarget.files;
    if (files && files.length > 0) {
      handleFile(files[0]);
    }
  };

  const handleFile = (file: File) => {
    if (!selectedPortfolioId) {
      return;
    }

    if (!file.name.endsWith('.xlsx')) {
      return;
    }

    setCurrentFile(file);
    setPreview(null);
    previewMutation.mutate({
      portfolioId: selectedPortfolioId as number,
      file,
    });
  };

  const handlePreviewSuccess = (data: ImportPreview) => {
    setPreview(data);
  };

  const handleCommit = () => {
    if (!currentFile || !selectedPortfolioId) {
      return;
    }

    commitMutation.mutate(
      {
        portfolioId: selectedPortfolioId as number,
        file: currentFile,
      },
      {
        onSuccess: (data) => {
          navigate(
            `/portfolios/${selectedPortfolioId as number}/imports/${data.id}`
          );
        },
      }
    );
  };

  const handleCancel = () => {
    setCurrentFile(null);
    setPreview(null);
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

  const handleBatchClick = (batchId: number) => {
    navigate(
      `/portfolios/${selectedPortfolioId as number}/imports/${batchId}`
    );
  };

  React.useEffect(() => {
    if (previewMutation.isSuccess && previewMutation.data) {
      handlePreviewSuccess(previewMutation.data);
    }
  }, [previewMutation.isSuccess, previewMutation.data]);

  if (pocketsLoading) {
    return (
      <Box display="flex" justifyContent="center" p={4}>
        <CircularProgress />
      </Box>
    );
  }

  const hasErrorRows =
    preview &&
    preview.rows.some((r) => r.row_status === 'error' || r.row_status === 'unrecognized');
  const canCommit =
    preview &&
    !hasErrorRows &&
    preview.existing_batch_id === null;

  return (
    <Box>
      <Typography variant="h4" component="h1" gutterBottom>
        Import danych
      </Typography>

      <Typography
        variant="body2"
        color="text.secondary"
        gutterBottom
        sx={{ mb: 3 }}
      >
        Importuj operacje z plików banków (Excel .xlsx)
      </Typography>

      <FormControl sx={{ minWidth: 200, mb: 3 }}>
        <InputLabel>Portfel</InputLabel>
        <Select
          value={selectedPortfolioId}
          onChange={handlePortfolioChange}
          label="Portfel"
        >
          <MenuItem value="">
            <em>Wybierz portfel</em>
          </MenuItem>
          {pockets?.map((pocket) => (
            <MenuItem key={pocket.id} value={pocket.id}>
              {pocket.name}
            </MenuItem>
          ))}
        </Select>
      </FormControl>

      {selectedPortfolioId && (
        <>
          <Paper
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            sx={{
              p: 4,
              textAlign: 'center',
              backgroundColor: dragActive
                ? 'action.hover'
                : 'background.paper',
              border: '2px dashed',
              borderColor: dragActive ? 'primary.main' : 'divider',
              cursor: 'pointer',
              transition: 'all 0.3s ease',
              mb: 4,
            }}
          >
            <input
              type="file"
              accept=".xlsx"
              onChange={handleFileInput}
              style={{ display: 'none' }}
              id="file-input"
              disabled={previewMutation.isPending || commitMutation.isPending}
            />
            <label
              htmlFor="file-input"
              style={{ cursor: 'pointer', display: 'block' }}
            >
              <CloudUploadIcon
                sx={{
                  fontSize: 48,
                  color: 'primary.main',
                  mb: 2,
                }}
              />
              <Typography variant="h6" gutterBottom>
                {previewMutation.isPending
                  ? 'Generowanie podglądu...'
                  : 'Przeciągnij plik Excel tutaj'}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                lub kliknij aby wybrać plik (.xlsx, maksymalnie 10 MB)
              </Typography>
            </label>
          </Paper>

          {preview && (
            <Box sx={{ mb: 4 }}>
              <Alert severity="info" sx={{ mb: 3 }}>
                Podgląd nie jest zapisywany — dane trafią do systemu dopiero
                po zatwierdzeniu.
              </Alert>

              {preview.existing_batch_id !== null && (
                <Alert severity="warning" sx={{ mb: 3 }}>
                  Ten plik został już zatwierdzony (
                  <MuiLink
                    component="button"
                    onClick={() =>
                      handleBatchClick(preview.existing_batch_id as number)
                    }
                    sx={{ cursor: 'pointer' }}
                  >
                    przejdź do paczki
                  </MuiLink>
                  )
                </Alert>
              )}

              <ReconciliationReportCard
                reconciliation={preview.reconciliation}
              />

              <ImportRowsTable rows={preview.rows} />

              <Box sx={{ display: 'flex', gap: 2 }}>
                <Button
                  variant="contained"
                  color="primary"
                  onClick={handleCommit}
                  disabled={!canCommit || commitMutation.isPending}
                >
                  {commitMutation.isPending
                    ? 'Zatwierdzanie...'
                    : 'Zatwierdź import'}
                </Button>
                <Button
                  variant="outlined"
                  onClick={handleCancel}
                  disabled={commitMutation.isPending}
                >
                  Anuluj
                </Button>
                {!canCommit && preview.existing_batch_id === null && (
                  <Typography variant="body2" color="warning.main" sx={{ alignSelf: 'center' }}>
                    Import zawiera wiersze z błędami/nieznane
                  </Typography>
                )}
              </Box>
            </Box>
          )}

          {importsLoading ? (
            <Box display="flex" justifyContent="center" p={4}>
              <CircularProgress />
            </Box>
          ) : imports && imports.length > 0 ? (
            <TableContainer component={Paper}>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Plik</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell>Data</TableCell>
                    <TableCell align="right">Akcje</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {imports.map((batch) => (
                    <TableRow key={batch.id} hover>
                      <TableCell>{batch.filename}</TableCell>
                      <TableCell>
                        <Chip
                          label={getStatusLabel(batch.status)}
                          color={getStatusColor(batch.status)}
                          size="small"
                        />
                      </TableCell>
                      <TableCell>
                        {dayjs(batch.created_at).format('DD.MM.YYYY HH:mm')}
                      </TableCell>
                      <TableCell align="right">
                        <Button
                          size="small"
                          onClick={() => handleBatchClick(batch.id)}
                        >
                          Szczegóły
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          ) : (
            <Paper sx={{ p: 4, textAlign: 'center' }}>
              <Typography color="text.secondary">
                Brak importów dla wybranego portfela
              </Typography>
            </Paper>
          )}
        </>
      )}
    </Box>
  );
};

export default ImportPage;

