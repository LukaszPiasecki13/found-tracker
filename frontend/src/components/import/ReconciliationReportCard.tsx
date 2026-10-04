import React from 'react';
import {
  Card,
  CardContent,
  Typography,
  Alert,
  List,
  ListItem,
  ListItemText,
  Divider,
} from '@mui/material';
import type { ReconciliationReport } from '../../types/api';

interface ReconciliationReportCardProps {
  reconciliation: ReconciliationReport | null;
}

export const ReconciliationReportCard: React.FC<
  ReconciliationReportCardProps
> = ({ reconciliation }) => {
  if (!reconciliation) {
    return null;
  }

  return (
    <Card sx={{ mb: 3 }}>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Raport zgodności
        </Typography>
        {!reconciliation.matched && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            Dane importu nie zgadzają się z wyliczeniami systemu
          </Alert>
        )}
        {reconciliation.ledger_error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {reconciliation.ledger_error}
          </Alert>
        )}

        {reconciliation.differences.length > 0 && (
          <>
            <Typography variant="subtitle2" gutterBottom sx={{ mt: 2 }}>
              Różnice:
            </Typography>
            <List>
              {reconciliation.differences.map((diff, idx) => (
                <ListItem key={idx}>
                  <ListItemText
                    primary={diff.field}
                    secondary={`Oczekiwane: ${diff.expected}, Rzeczywiste: ${diff.actual}`}
                  />
                </ListItem>
              ))}
            </List>
          </>
        )}

        {reconciliation.closed_profit_reported !== null && (
          <>
            <Divider sx={{ my: 2 }} />
            <Typography variant="body2">
              Zysk ze zamkniętych pozycji (raportowany):
              {' '}
              <strong>
                {reconciliation.closed_profit_reported.toFixed(2)}
              </strong>
            </Typography>
          </>
        )}
      </CardContent>
    </Card>
  );
};
