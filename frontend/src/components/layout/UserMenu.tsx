import { useState } from 'react';
import {
  Avatar,
  Box,
  ButtonBase,
  Divider,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Typography,
} from '@mui/material';
import { Logout as LogoutIcon, Settings as SettingsIcon } from '@mui/icons-material';
import { useAuth } from '../../contexts/AuthContext';

interface UserMenuProps {
  onNavigate?: () => void;
  onOpenSettings?: () => void;
  collapsed?: boolean;
}

/**
 * User menu pinned to the bottom of the sidebar (like `UserMenu` in waterworks): an initial
 * avatar and the e-mail; the menu opens upwards with "Ustawienia" and "Wyloguj się".
 */
export default function UserMenu({ onNavigate, onOpenSettings, collapsed = false }: UserMenuProps) {
  const { user, logout } = useAuth();
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);

  if (!user) return null;

  const close = () => setAnchorEl(null);
  const initial = user.email.charAt(0).toUpperCase();

  return (
    <Box sx={{ borderTop: 1, borderColor: 'divider', px: 1, py: 2 }}>
      <ButtonBase
        onClick={(event) => setAnchorEl(event.currentTarget)}
        aria-haspopup="menu"
        aria-expanded={Boolean(anchorEl)}
        sx={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: collapsed ? 'center' : 'flex-start',
          gap: 1.5,
          px: 1.5,
          py: 1,
          borderRadius: 2,
          textAlign: 'left',
          '&:hover': { bgcolor: 'action.hover' },
        }}
      >
        <Avatar
          sx={{
            width: 32,
            height: 32,
            fontSize: 14,
            fontWeight: 600,
            bgcolor: 'primary.light',
            color: 'primary.contrastText',
          }}
        >
          {initial}
        </Avatar>
        {!collapsed && (
          <Typography variant="body2" noWrap sx={{ fontWeight: 500, minWidth: 0 }}>
            {user.email}
          </Typography>
        )}
      </ButtonBase>

      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={close}
        anchorOrigin={{ vertical: 'top', horizontal: 'left' }}
        transformOrigin={{ vertical: 'bottom', horizontal: 'left' }}
        slotProps={{ paper: { sx: { width: 224 } } }}
      >
        {onOpenSettings && (
          <MenuItem
            onClick={() => {
              close();
              onOpenSettings();
              onNavigate?.();
            }}
          >
            <ListItemIcon>
              <SettingsIcon fontSize="small" />
            </ListItemIcon>
            <ListItemText>Ustawienia</ListItemText>
          </MenuItem>
        )}
        {onOpenSettings && <Divider />}
        <MenuItem
          onClick={() => {
            close();
            logout();
          }}
          sx={{ color: 'error.main' }}
        >
          <ListItemIcon sx={{ color: 'inherit' }}>
            <LogoutIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText>Wyloguj się</ListItemText>
        </MenuItem>
      </Menu>
    </Box>
  );
}
