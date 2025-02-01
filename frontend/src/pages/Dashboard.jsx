import React, { useState, useEffect } from "react";
import { styled, createTheme, ThemeProvider } from "@mui/material/styles";
import CssBaseline from "@mui/material/CssBaseline";
import Box from "@mui/material/Box";
import Grid from "@mui/material/Grid";
import Paper from "@mui/material/Paper";
import Toolbar from "@mui/material/Toolbar";
import Title from "../components/Title";
import { DatePicker } from "@mui/x-date-pickers/DatePicker";
import dayjs from "dayjs";
import CircularProgress from "@mui/material/CircularProgress";
import { LocalizationProvider } from "@mui/x-date-pickers";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";

import GraphBlock from "../components/GraphBlock";
import RecentScore from "../components/RecentScore";
import SideBar from "../components/Bars/SideBar";
import AppBar from "../components/Bars/AppBar";
import PageContainer from "../components/PageContainer";
import Pockets from "../components/Pockets";
import api from "../api";
import { mergeWithObject } from "../components/utils";
import DateRangePicker from "../components/DateRangePicker";

const defaultTheme = createTheme();

export default function Dashboard() {
  const [open, setOpen] = React.useState(true);
  const toggleDrawer = () => {
    setOpen(!open);
  };
  const [startDate, setStartDate] = React.useState(dayjs().subtract(1, "year"));
  const [endDate, setEndDate] = React.useState(dayjs());
  const [isDataLoading, setIsDataLoading] = React.useState(true);
  const [profitVector, setProfitVector] = React.useState([]);

  const handleDateChange = (newStartDate, newEndDate) => {
    setStartDate(newStartDate);
    setEndDate(newEndDate);
    getPocketVectors(newStartDate, newEndDate);
  };

  const getPocketVectors = async (start, end) => {
    setIsDataLoading(true);
    try {
      const res = await api.get("/api/pocket-vectors", {
        params: {
          pocketName: null,
          startDate: start.format("YYYY-MM-DD"),
          endDate: end.format("YYYY-MM-DD"),
          interval: "1d",
          vectors: JSON.stringify(["profit_vector"]),
        },
      });
      if (Object.keys(res.data).length !== 0) {
        const date = res.data.date.map((date) => date.slice(0, 10));
        const mergedProfitVectors = mergeWithObject(date, {
          profit_vector: res.data.profit_vector,
        });
        setProfitVector(mergedProfitVectors);
      } else {
        setProfitVector([]);
      }
    } catch (err) {
      alert(err.response.data.error.message);
    } finally {
      setIsDataLoading(false);
    }
  };

  

  React.useEffect(() => {
    const fetchData = async () => {
      await Promise.all([getPocketVectors(startDate, endDate)]);
    };
    fetchData();
  }, []);

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
                height: 450,
              }}
            >
              <Grid>
                <Title sx={{ marginBottom: "8px" }}>Portfolio Score</Title>
              </Grid>

              <DateRangePicker
                initialStartDate={startDate}
                initialEndDate={endDate}
                onDateChange={handleDateChange}
              />

              {isDataLoading ? (
                <CircularProgress />
              ) : (
                <GraphBlock
                  type="line"
                  data={profitVector}
                  dataKey={"profit_vector"}
                />
              )}
            </Paper>
          </Grid>
          <Grid item xs={12} md={4} lg={3}>
            <Paper
              sx={{
                p: 2,
                display: "flex",
                flexDirection: "column",
                height: 240,
              }}
            >
              <RecentScore value={profitVector && profitVector.length > 0 ? profitVector[profitVector.length - 1].profit_vector : '--'} />
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
