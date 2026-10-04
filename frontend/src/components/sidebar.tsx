import React from 'react';
import { Link as RouterLink, useLocation } from 'react-router-dom';
import {
  Drawer,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Divider,
  Toolbar,
  Box,
  useTheme,
  useMediaQuery,
  Typography,
} from '@mui/material';
import { Collapse, CircularProgress } from '@mui/material';
import { ExpandLess, ExpandMore } from '@mui/icons-material';
import { useState } from 'react';
import { usePockets } from '../hooks/usePockets';
import {
  Dashboard as DashboardIcon,
  AccountBalance as PocketIcon,
  SwapHoriz as OperationsIcon,
  CompareArrows as CompareIcon,
  CloudUpload as ImportIcon,
} from '@mui/icons-material';

const drawerWidth = 240;

interface SidebarProps {
  mobileOpen: boolean;
  onDrawerToggle: () => void;
}

const menuItems = [
  { text: 'Dashboard', icon: <DashboardIcon />, path: '/' },
  { text: 'Operacje', icon: <OperationsIcon />, path: '/operations' },
  { text: 'Import', icon: <ImportIcon />, path: '/import' },
  { text: 'Porównaj portfele', icon: <CompareIcon />, path: '/compare' },
];

const Sidebar: React.FC<SidebarProps> = ({ mobileOpen, onDrawerToggle }) => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const { data: pockets, isLoading: pocketsLoading, error: pocketsError } = usePockets();

  const drawerContent = (
    <Box>
      <Toolbar>
        <Typography variant="h6" sx={{ fontWeight: 700 }}>
          Portfele
        </Typography>
      </Toolbar>
      <Divider />
      
      <List>
        {menuItems.map((item) => (
          <ListItem key={item.text} disablePadding>
            <ListItemButton
              component={RouterLink}
              to={item.path}
              selected={location.pathname === item.path}
              onClick={isMobile ? onDrawerToggle : undefined}
            >
              <ListItemIcon>{item.icon}</ListItemIcon>
              <ListItemText primary={item.text} />
            </ListItemButton>
          </ListItem>
        ))}
      </List>
      
      <Divider />
      
      <List>
        <ListItem disablePadding>
          <ListItemButton onClick={() => setOpen(!open)}>
            <ListItemIcon>
              <PocketIcon />
            </ListItemIcon>
            <ListItemText
              primary="Moje Portfele"
              primaryTypographyProps={{ variant: 'caption', color: 'text.secondary' }}
            />
            {open ? <ExpandLess /> : <ExpandMore />}
          </ListItemButton>
        </ListItem>

        <Collapse in={open} timeout="auto" unmountOnExit>
          <List component="div" disablePadding>
            {pocketsLoading && (
              <ListItem>
                <ListItemText>
                  <CircularProgress size={18} />
                </ListItemText>
              </ListItem>
            )}

            {pocketsError && (
              <ListItem>
                <ListItemText primary="Błąd ładowania" />
              </ListItem>
            )}

            {pockets?.map((p) => (
              <ListItem key={p.id} disablePadding>
                <ListItemButton
                  component={RouterLink}
                  to={`/pockets/${encodeURIComponent(p.name)}`}
                  onClick={isMobile ? onDrawerToggle : undefined}
                  sx={{ pl: 4 }}
                  selected={location.pathname === `/pockets/${encodeURIComponent(p.name)}`}
                >
                  <ListItemText primary={p.name} />
                </ListItemButton>
              </ListItem>
            ))}
          </List>
        </Collapse>
      </List>
    </Box>
  );

  return (
    <Box
      component="nav"
      sx={{ width: { md: drawerWidth }, flexShrink: { md: 0 } }}
    >
      {/* Mobile drawer */}
      <Drawer
        variant="temporary"
        open={mobileOpen}
        onClose={onDrawerToggle}
        ModalProps={{ keepMounted: true }}
        sx={{
          display: { xs: 'block', md: 'none' },
          '& .MuiDrawer-paper': { boxSizing: 'border-box', width: drawerWidth },
        }}
      >
        {drawerContent}
      </Drawer>

      {/* Desktop drawer */}
      <Drawer
        variant="permanent"
        sx={{
          display: { xs: 'none', md: 'block' },
          '& .MuiDrawer-paper': { boxSizing: 'border-box', width: drawerWidth },
        }}
        open
      >
        {drawerContent}
      </Drawer>
    </Box>
  );
};

export default Sidebar;
