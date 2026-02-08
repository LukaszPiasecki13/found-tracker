import React, { useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import {
  Container,
  Box,
  Card,
  CardContent,
  Typography,
  TextField,
  Button,
  Link,
  CircularProgress,
  MenuItem,
} from '@mui/material';
import { useAuth } from '../contexts/AuthContext';

const RegisterPage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [mainCurrency, setMainCurrency] = useState('PLN');
  const [isLoading, setIsLoading] = useState(false);
  const [errors, setErrors] = useState<{ [key: string]: string }>({});
  const { register } = useAuth();

  const validate = (): boolean => {
    const newErrors: { [key: string]: string } = {};

    if (!email) {
      newErrors.email = 'Email jest wymagany';
    } else if (!/\S+@\S+\.\S+/.test(email)) {
      newErrors.email = 'Nieprawidłowy format email';
    }

    if (!password) {
      newErrors.password = 'Hasło jest wymagane';
    } else if (password.length < 8) {
      newErrors.password = 'Hasło musi mieć co najmniej 8 znaków';
    }

    if (password !== confirmPassword) {
      newErrors.confirmPassword = 'Hasła nie są identyczne';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validate()) {
      return;
    }

    setIsLoading(true);

    try {
      await register({ email, password, main_currency: mainCurrency });
    } catch (error) {
      // Error is already handled in AuthContext with snackbar
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Container maxWidth="sm">
      <Box
        sx={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          py: 4,
        }}
      >
        <Card sx={{ width: '100%' }}>
          <CardContent sx={{ p: 4 }}>
            <Typography variant="h4" component="h1" gutterBottom align="center">
              FoundTracker
            </Typography>
            <Typography variant="h5" component="h2" gutterBottom align="center" color="text.secondary">
              Zarejestruj się
            </Typography>

            <Box component="form" onSubmit={handleSubmit} sx={{ mt: 3 }}>
              <TextField
                fullWidth
                label="Email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                margin="normal"
                required
                autoFocus
                disabled={isLoading}
                error={!!errors.email}
                helperText={errors.email}
              />
              <TextField
                fullWidth
                label="Hasło"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                margin="normal"
                required
                disabled={isLoading}
                error={!!errors.password}
                helperText={errors.password}
              />
              <TextField
                fullWidth
                label="Potwierdź hasło"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                margin="normal"
                required
                disabled={isLoading}
                error={!!errors.confirmPassword}
                helperText={errors.confirmPassword}
              />
              <TextField
                fullWidth
                select
                label="Główna waluta"
                value={mainCurrency}
                onChange={(e) => setMainCurrency(e.target.value)}
                margin="normal"
                disabled={isLoading}
              >
                <MenuItem value="PLN">PLN - Polski złoty</MenuItem>
                <MenuItem value="USD">USD - Dolar amerykański</MenuItem>
                <MenuItem value="EUR">EUR - Euro</MenuItem>
              </TextField>

              <Button
                type="submit"
                fullWidth
                variant="contained"
                size="large"
                sx={{ mt: 3, mb: 2 }}
                disabled={isLoading}
              >
                {isLoading ? <CircularProgress size={24} /> : 'Zarejestruj'}
              </Button>

              <Box sx={{ textAlign: 'center', mt: 2 }}>
                <Typography variant="body2" color="text.secondary">
                  Masz już konto?{' '}
                  <Link component={RouterLink} to="/login" underline="hover">
                    Zaloguj się
                  </Link>
                </Typography>
              </Box>
            </Box>
          </CardContent>
        </Card>
      </Box>
    </Container>
  );
};

export default RegisterPage;
