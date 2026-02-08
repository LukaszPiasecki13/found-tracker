import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom"
import { ThemeProvider } from "@mui/material/styles"
import CssBaseline from "@mui/material/CssBaseline"
import { theme } from "./lib/theme"
import { AuthProvider } from "./contexts/AuthContext"
import ProtectedRoute from "./components/ProtectedRoute"
import MainLayout from "./components/MainLayout"
import LoginPage from "./pages/LoginPage"
import RegisterPage from "./pages/RegisterPage"
import DashboardPage from "./pages/DashboardPage"
import PocketDetailsPage from "./pages/PocketDetailsPage"
import PocketHistoryPage from "./pages/PocketHistoryPage"
import OperationsPage from "./pages/OperationsPage"


function App() {
    return (
    <BrowserRouter>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <AuthProvider>
          <Routes>
            {/* Public routes */}
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />

            {/* Protected routes */}
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <MainLayout>
                    <DashboardPage />
                  </MainLayout>
                </ProtectedRoute>
              }
            />
            
            <Route
              path="/pockets/:slug"
              element={
                <ProtectedRoute>
                  <MainLayout>
                    <PocketDetailsPage />
                  </MainLayout>
                </ProtectedRoute>
              }
            />

            <Route
              path="/pockets/:slug/history"
              element={
                <ProtectedRoute>
                  <MainLayout>
                    <PocketHistoryPage />
                  </MainLayout>
                </ProtectedRoute>
              }
            />

            <Route
              path="/operations"
              element={
                <ProtectedRoute>
                  <MainLayout>
                    <OperationsPage />
                  </MainLayout>
                </ProtectedRoute>
              }
            />
            
            {/* Fallback */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </AuthProvider>
      </ThemeProvider>
    </BrowserRouter>
  )
}

export default App;
