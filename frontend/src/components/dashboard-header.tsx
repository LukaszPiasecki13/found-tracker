// src/components/dashboard-header/DashboardHeader.tsx
import React, { useState } from "react"
import { Link as RouterLink, useLocation } from "react-router-dom"
import {
  AppBar,
  Toolbar,
  Typography,
  Button,
  IconButton,
  Box,
  Menu,
  MenuItem,
  Tabs,
  Tab,
} from "@mui/material"
import MenuIcon from "@mui/icons-material/Menu"
import {
  Notifications as NotificationsIcon,
  AccountCircle as AccountCircleIcon,
  Add as AddIcon,
  Settings as SettingsIcon,
  Logout as LogoutIcon,
} from "@mui/icons-material"
import { useAuth } from "../contexts/AuthContext"
// import { AddTransactionDialog } from "./add-transaction-dialog"

interface DashboardHeaderProps {
  onMenuClick?: () => void;
}

export default function DashboardHeader({ onMenuClick }: DashboardHeaderProps) {

  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null)
  const [openDialog, setOpenDialog] = useState(false)
  const location = useLocation() 
  const { logout, user } = useAuth();

  const handleMenu = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget)
  }

  const handleClose = () => {
    setAnchorEl(null)
  }

  const handleLogout = () => {
    handleClose();
    logout();
  };

  const getTabValue = () => {
    const pathname = location.pathname
    if (pathname === "/") return 0
    if (pathname.startsWith("/portfolio") || pathname.startsWith("/pockets")) return 1
    if (pathname === "/transactions" || pathname === "/operations") return 2
    if (pathname === "/analytics") return 3
    if (pathname === "/alerts") return 4
    return 0
  }

  return (
    <>
      <AppBar position="static" color="default" elevation={1}>
        <Toolbar>
          <IconButton
            size="large"
            edge="start"
            color="inherit"
            aria-label="menu"
            sx={{ mr: 2, display: { md: 'none' } }}
            onClick={onMenuClick}
          >
            <MenuIcon />
          </IconButton>
          <Typography variant="h6" component="div" sx={{ fontWeight: 700, mr: 4 }}>
            FoundTracker
          </Typography>

          <Tabs value={getTabValue()} sx={{ flexGrow: 1, display: { xs: 'none', md: 'flex' } }}>
            <Tab label="Dashboard" component={RouterLink} to="/" />
            <Tab label="Portfele" />
            <Tab label="Operacje" component={RouterLink} to="/operations" />
            <Tab label="Analizy" />
          </Tabs>

          <Box sx={{ display: "flex", gap: 1, alignItems: 'center' }}>
            <Typography variant="body2" sx={{ display: { xs: 'none', sm: 'block' }, mr: 1 }}>
              {user?.email}
            </Typography>
            
            <Button 
              variant="outlined" 
              startIcon={<AddIcon />} 
              onClick={() => setOpenDialog(true)}
              sx={{ display: { xs: 'none', sm: 'inline-flex' } }}
            >
              Dodaj transakcję
            </Button>

            <IconButton color="inherit" sx={{ display: { xs: 'none', sm: 'inline-flex' } }}>
              <NotificationsIcon />
            </IconButton>

            <IconButton color="inherit" onClick={handleMenu}>
              <AccountCircleIcon />
            </IconButton>

            <Menu anchorEl={anchorEl} open={Boolean(anchorEl)} onClose={handleClose}>
              <MenuItem component={RouterLink} to="/settings" onClick={handleClose}>
                <SettingsIcon sx={{ mr: 1 }} fontSize="small" />
                Ustawienia
              </MenuItem>
              <MenuItem onClick={handleLogout}>
                <LogoutIcon sx={{ mr: 1 }} fontSize="small" />
                Wyloguj
              </MenuItem>
            </Menu>
          </Box>
        </Toolbar>
      </AppBar>

      {/* <AddTransactionDialog open={openDialog} onClose={() => setOpenDialog(false)} /> */}
    </>
  )
}
