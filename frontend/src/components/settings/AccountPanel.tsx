import { Box, Chip, Divider, Typography } from '@mui/material';
import { useAuth } from '../../contexts/AuthContext';

export default function AccountPanel() {
  const { user } = useAuth();

  return (
    <Box>
      <Box sx={{ px: { xs: 2, sm: 3 }, pt: 3, pb: 2 }}>
        <Typography variant="h6" component="h2" sx={{ fontWeight: 600 }}>
          Moje konto
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
          Dane profilu zalogowanego użytkownika
        </Typography>
      </Box>
      <Divider />
      <Box sx={{ px: { xs: 2, sm: 3 }, py: 3 }}>
        {user ? (
          <Box sx={{ display: 'grid', gridTemplateColumns: 'max-content 1fr', gap: 2, alignItems: 'center' }}>
            <Typography variant="body2" color="text.secondary">
              E-mail
            </Typography>
            <Typography variant="body2" sx={{ fontWeight: 500 }}>
              {user.email}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Status
            </Typography>
            <Box>
              <Chip
                size="small"
                label={user.is_active ? 'Aktywne' : 'Nieaktywne'}
                color={user.is_active ? 'success' : 'default'}
                variant="outlined"
              />
            </Box>
          </Box>
        ) : (
          <Typography variant="body2" color="text.secondary">
            Ładowanie profilu...
          </Typography>
        )}
      </Box>
    </Box>
  );
}
