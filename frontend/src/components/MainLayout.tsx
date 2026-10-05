import React, { useState } from 'react';
import { Box } from '@mui/material';
import { useSidebarDrawer } from '../hooks/useSidebarDrawer';
import Sidebar from './layout/Sidebar';
import Topbar from './layout/Topbar';
import SettingsDialog from './settings/SettingsDialog';

interface MainLayoutProps {
  children: React.ReactNode;
}

/**
 * App shell shared with waterworks-monitoring-platform: sidebar on the left (user menu at
 * its bottom), topbar above the content, settings in a fullscreen dialog.
 */
const MainLayout: React.FC<MainLayoutProps> = ({ children }) => {
  const drawer = useSidebarDrawer();
  const [collapsed, setCollapsed] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);

  return (
    <Box sx={{ display: 'flex', height: '100dvh', bgcolor: 'background.default' }}>
      <Sidebar
        isOpen={drawer.isOpen}
        isDesktop={drawer.isDesktop}
        onClose={drawer.close}
        collapsed={collapsed}
        onOpenSettings={() => setSettingsOpen(true)}
      />

      <Box sx={{ display: 'flex', flexDirection: 'column', flex: 1, minWidth: 0 }}>
        <Topbar
          onMenuClick={drawer.toggle}
          isSidebarOpen={drawer.isOpen}
          collapsed={collapsed}
          onToggleSidebar={() => setCollapsed((c) => !c)}
        />
        <Box component="main" sx={{ flex: 1, minWidth: 0, overflow: 'auto', p: 3 }}>
          {children}
        </Box>
      </Box>

      <SettingsDialog open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </Box>
  );
};

export default MainLayout;
