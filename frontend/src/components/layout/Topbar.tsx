import React from 'react';
import { AppBar, Box, IconButton, Toolbar, Typography } from '@mui/material';
import {
  ChevronLeft as ChevronLeftIcon,
  ChevronRight as ChevronRightIcon,
  Menu as MenuIcon,
} from '@mui/icons-material';

export const TOPBAR_HEIGHT = 64;

interface TopbarProps {
  onMenuClick?: () => void;
  isSidebarOpen?: boolean;
  collapsed?: boolean;
  onToggleSidebar?: () => void;
  /** Slot on the right (AlarmCounter/EnvironmentSwitcher in waterworks). */
  actions?: React.ReactNode;
}

/**
 * Top bar with the same structure as `Topbar` in waterworks-monitoring-platform: a hamburger
 * (< lg) or collapse toggle (>= lg) with the title and subtitle on the left, actions on the
 * right. The user menu lives in the sidebar (`UserMenu`), not here.
 */
export default function Topbar({
  onMenuClick,
  isSidebarOpen = false,
  collapsed = false,
  onToggleSidebar,
  actions,
}: TopbarProps) {
  const collapseLabel = collapsed ? 'Rozwiń pasek boczny' : 'Zwiń pasek boczny';

  return (
    <AppBar
      position="sticky"
      color="inherit"
      elevation={0}
      sx={{
        bgcolor: 'background.paper',
        borderBottom: 1,
        borderColor: 'divider',
        boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
      }}
    >
      <Toolbar sx={{ height: TOPBAR_HEIGHT, gap: 1, px: { xs: 2, sm: 3 } }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 0, flexGrow: 1 }}>
          <IconButton
            onClick={onMenuClick}
            aria-label="Przełącz menu"
            aria-expanded={isSidebarOpen}
            sx={{ display: { lg: 'none' }, color: 'text.primary' }}
          >
            <MenuIcon />
          </IconButton>
          <IconButton
            onClick={onToggleSidebar}
            aria-label={collapseLabel}
            title={collapseLabel}
            sx={{ display: { xs: 'none', lg: 'inline-flex' }, color: 'text.primary' }}
          >
            {collapsed ? <ChevronRightIcon /> : <ChevronLeftIcon />}
          </IconButton>
          <Box sx={{ minWidth: 0 }}>
            <Typography variant="h6" component="h1" noWrap sx={{ fontWeight: 600, lineHeight: 1.3 }}>
              FundTracker
            </Typography>
            <Typography
              variant="caption"
              color="text.secondary"
              noWrap
              sx={{ display: { xs: 'none', sm: 'block' } }}
            >
              Panel śledzenia portfeli inwestycyjnych
            </Typography>
          </Box>
        </Box>

        {actions && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flex: 'none' }}>{actions}</Box>
        )}
      </Toolbar>
    </AppBar>
  );
}
