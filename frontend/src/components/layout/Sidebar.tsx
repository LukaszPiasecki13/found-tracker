import { useState } from 'react';
import { Link as RouterLink, useLocation } from 'react-router-dom';
import {
  Box,
  CircularProgress,
  Collapse,
  Drawer,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Tooltip,
  Typography,
} from '@mui/material';
import {
  AccountBalance as PocketIcon,
  AccountBalanceWallet as AccountIcon,
  CompareArrows as CompareIcon,
  Dashboard as DashboardIcon,
  ExpandLess,
  ExpandMore,
  SwapHoriz as OperationsIcon,
} from '@mui/icons-material';
import { usePockets } from '../../hooks/usePockets';
import { TOPBAR_HEIGHT } from './Topbar';
import UserMenu from './UserMenu';

export const SIDEBAR_WIDTH = 256;
export const SIDEBAR_WIDTH_COLLAPSED = 64;

interface NavItem {
  label: string;
  path: string;
  icon: React.ReactNode;
}

const navItems: NavItem[] = [
  { label: 'Dashboard', path: '/', icon: <DashboardIcon /> },
  { label: 'Operacje', path: '/operations', icon: <OperationsIcon /> },
  { label: 'Porównaj portfele', path: '/compare', icon: <CompareIcon /> },
  { label: 'Wykresy konta', path: '/account/charts', icon: <AccountIcon /> },
];

interface SidebarProps {
  isOpen: boolean;
  isDesktop: boolean;
  onClose: () => void;
  collapsed: boolean;
  onOpenSettings: () => void;
}

const itemSx = {
  minHeight: 44,
  borderRadius: 2,
  px: 1.5,
  gap: 1.5,
  '&.Mui-selected': {
    bgcolor: 'rgba(13, 155, 145, 0.1)',
    color: 'primary.dark',
    fontWeight: 600,
    '&:hover': { bgcolor: 'rgba(13, 155, 145, 0.16)' },
  },
} as const;

/**
 * Left navigation, structured like `PlatformSidebar` in waterworks-monitoring-platform:
 * a static, collapsible column from `lg` up, a drawer below it, and the user menu pinned
 * to the bottom.
 */
export default function Sidebar({
  isOpen,
  isDesktop,
  onClose,
  collapsed,
  onOpenSettings,
}: SidebarProps) {
  const location = useLocation();
  const [pocketsOpen, setPocketsOpen] = useState(false);
  const { data: pockets, isLoading, error } = usePockets();

  // Only the static column collapses; the drawer always shows labels.
  const compact = isDesktop && collapsed;
  const closeDrawer = isDesktop ? undefined : onClose;

  const renderNavButton = (item: NavItem) => {
    const button = (
      <ListItemButton
        component={RouterLink}
        to={item.path}
        selected={location.pathname === item.path}
        onClick={closeDrawer}
        sx={{ ...itemSx, justifyContent: compact ? 'center' : 'flex-start' }}
      >
        <ListItemIcon sx={{ minWidth: 0, color: 'inherit', opacity: 0.7 }}>{item.icon}</ListItemIcon>
        {!compact && <ListItemText primary={item.label} slotProps={{ primary: { variant: 'body2', fontWeight: 'inherit' } }} />}
      </ListItemButton>
    );
    return compact ? (
      <Tooltip title={item.label} placement="right">
        {button}
      </Tooltip>
    ) : (
      button
    );
  };

  const content = (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', overflowY: 'auto' }}>
      <Box component="nav" sx={{ flex: 1, py: 2, px: compact ? 0.5 : 1 }}>
        {!compact && (
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{ display: 'block', px: 1.5, py: 1, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}
          >
            Nawigacja
          </Typography>
        )}
        <List disablePadding sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
          {navItems.map((item) => (
            <ListItem key={item.path} disablePadding>
              {renderNavButton(item)}
            </ListItem>
          ))}
        </List>

        {!compact && (
          <List disablePadding sx={{ mt: 2 }}>
            <ListItem disablePadding>
              <ListItemButton onClick={() => setPocketsOpen(!pocketsOpen)} sx={itemSx}>
                <ListItemIcon sx={{ minWidth: 0, color: 'inherit', opacity: 0.7 }}>
                  <PocketIcon />
                </ListItemIcon>
                <ListItemText primary="Moje portfele" slotProps={{ primary: { variant: 'body2' } }} />
                {pocketsOpen ? <ExpandLess /> : <ExpandMore />}
              </ListItemButton>
            </ListItem>
            <Collapse in={pocketsOpen} timeout="auto" unmountOnExit>
              <List component="div" disablePadding>
                {isLoading && (
                  <ListItem>
                    <CircularProgress size={18} />
                  </ListItem>
                )}
                {error && (
                  <ListItem>
                    <ListItemText primary="Błąd ładowania" />
                  </ListItem>
                )}
                {pockets?.map((p) => {
                  const path = `/pockets/${encodeURIComponent(p.name)}`;
                  return (
                    <ListItem key={p.id} disablePadding>
                      <ListItemButton
                        component={RouterLink}
                        to={path}
                        onClick={closeDrawer}
                        selected={location.pathname === path}
                        sx={{ ...itemSx, pl: 6 }}
                      >
                        <ListItemText primary={p.name} slotProps={{ primary: { variant: 'body2', fontWeight: 'inherit', noWrap: true } }} />
                      </ListItemButton>
                    </ListItem>
                  );
                })}
              </List>
            </Collapse>
          </List>
        )}
      </Box>

      <UserMenu onNavigate={closeDrawer} onOpenSettings={onOpenSettings} collapsed={compact} />
    </Box>
  );

  if (isDesktop) {
    return (
      <Box
        component="aside"
        sx={{
          flex: 'none',
          width: collapsed ? SIDEBAR_WIDTH_COLLAPSED : SIDEBAR_WIDTH,
          transition: 'width 300ms',
          bgcolor: 'background.paper',
          borderRight: 1,
          borderColor: 'divider',
          overflow: 'hidden',
        }}
      >
        {content}
      </Box>
    );
  }

  // Below `lg` the drawer sits under the topbar, like in waterworks.
  return (
    <Drawer
      variant="temporary"
      open={isOpen}
      onClose={onClose}
      slotProps={{
        root: { keepMounted: true },
        backdrop: { sx: { top: TOPBAR_HEIGHT } },
        paper: {
          sx: {
            top: TOPBAR_HEIGHT,
            height: `calc(100% - ${TOPBAR_HEIGHT}px)`,
            width: SIDEBAR_WIDTH,
            maxWidth: '85vw',
            boxSizing: 'border-box',
          },
        },
      }}
    >
      {content}
    </Drawer>
  );
}
