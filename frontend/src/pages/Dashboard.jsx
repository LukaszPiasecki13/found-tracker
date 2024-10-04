import React, { useState, useEffect } from "react";
import { styled, createTheme, ThemeProvider } from "@mui/material/styles";
import CssBaseline from "@mui/material/CssBaseline";
import Box from "@mui/material/Box";
import Grid from "@mui/material/Grid";
import Paper from "@mui/material/Paper";
import Toolbar from "@mui/material/Toolbar";
import Title from "../components/Title";

import Chart from "../components/Chart";
import RecentScore from "../components/RecentScore";
import SideBar from "../components/Bars/SideBar";
import AppBar from "../components/Bars/AppBar";
import PageContainer from "../components/PageContainer";
import Pockets from "../components/Pockets";
import api from "../api";

const defaultTheme = createTheme();

export default function Dashboard() {
  const [open, setOpen] = React.useState(true);
  const toggleDrawer = () => {
    setOpen(!open);
  };

  const [chartData, setData] = React.useState([]);

  const getProfitOverTime = () => {
    api
      .get("/api/profit-data", {
        params: {
          pocketName: null,
          startDate: "2023-07-22",
          endDate: "2024-07-22",
        },
      })
      .then((response) => {
        const chartDataa = {
          date: response.data.Date,
          value: response.data.Close,
        };
        setData(chartDataa);
      })
      .catch((error) => {
        console.error("Error fetching data:", error);
      });
  };

  React.useEffect(() => {
    getProfitOverTime();
  }, []);

  const [loading, setLoading] = React.useState(true);
  const [recentScoreValue, setRecentScoreValue] = React.useState(true);

  // Effect for setting the charging state
  React.useEffect(() => {
    if (chartData.value) {
      setLoading(false);
      setRecentScoreValue(chartData.value[chartData.value.length - 1]);
    } else {
      setLoading(true);
      setRecentScoreValue(0);
    }
  }, [chartData]);

  return (
    <ThemeProvider theme={defaultTheme}>
      <Box sx={{ display: "flex" }}>
        <CssBaseline />
        <AppBar open={open} toggleDrawer={toggleDrawer} />
        <SideBar open={open} toggleDrawer={toggleDrawer} />

        <PageContainer>
          <Grid item xs={12} md={8} lg={9}>
            <Paper
              sx={{
                p: 2,
                display: "flex",
                flexDirection: "column",
                height: 400,
              }}
            >
              <Title>Portfolio Score</Title>
              <Chart x={chartData.date} y={chartData.value} loading={loading} />
            </Paper>
          </Grid>
          {/* Recent Deposits */}
          <Grid item xs={12} md={4} lg={3}>
            <Paper
              sx={{
                p: 2,
                display: "flex",
                flexDirection: "column",
                height: 240,
              }}
            >
              <RecentScore value={recentScoreValue} />
            </Paper>
          </Grid>
          <Grid item xs={4}>
            <Paper sx={{ p: 2, display: "flex", flexDirection: "column" }}>
              <Pockets />
            </Paper>
          </Grid>
        </PageContainer>
      </Box>
    </ThemeProvider>
  );
}
