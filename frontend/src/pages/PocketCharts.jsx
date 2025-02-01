import * as React from "react";
import { useParams } from "react-router-dom";
import { styled, createTheme, ThemeProvider } from "@mui/material/styles";
import CssBaseline from "@mui/material/CssBaseline";
import Box from "@mui/material/Box";
import Grid from "@mui/material/Grid";
import Paper from "@mui/material/Paper";
import CircularProgress from "@mui/material/CircularProgress";
import { useNavigate, useLocation } from "react-router-dom";
import { DatePicker } from "@mui/x-date-pickers/DatePicker";
import dayjs from "dayjs";
import { LocalizationProvider } from "@mui/x-date-pickers";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";
import { Button } from "@mui/material";

import api from "../api";
import SideBar from "../components/Bars/SideBar";
import AppBar from "../components/Bars/AppBar";
import PageContainer from "../components/PageContainer";
import Title from "../components/Title";
import { mergeWithObject } from "../components/utils";
import DateRangePicker from "../components/DateRangePicker";
import GraphBlock from "../components/GraphBlock";

export default function PocketCharts() {
  const navigate = useNavigate();
  const location = useLocation();
  const pocketName = useParams().slug;
  const defaultTheme = createTheme();
  const [open, setOpen] = React.useState(true);
  const [participationSeries, setParticipationSeries] = React.useState([]);
  const [pocketVectors, setPocketVectors] = React.useState([]);
  const [assetVectors, setAssetVectors] = React.useState([]);
  const [assetClassVectors, setAssetClassVectors] = React.useState([]);
  const [isDataLoading, setIsDataLoading] = React.useState(true);

  const [startDate, setStartDate] = React.useState(dayjs().subtract(1, "year"));
  const [endDate, setEndDate] = React.useState(dayjs());

  const handleDateChange = (newStartDate, newEndDate) => {
    setStartDate(newStartDate);
    setEndDate(newEndDate);
    getPocketVectors(newStartDate, newEndDate);
  };

  const getPocketDetail = async () => {
    try {
      const res = await api.get("api/asset-allocations", {
        params: {
          pocket_name: pocketName,
        },
      });
      if (res.data.length !== 0) {
        const mergedData = merge(res.data);
        setParticipationSeries(mergedData);
      } else {
        setParticipationSeries([]);
      }
    } catch (err) {
      alert(err.response.data.error.message);
    }
  };

  const getPocketVectors = async (start, end) => {
    setIsDataLoading(true);
    try {
      const res = await api.get("/api/pocket-vectors", {
        params: {
          pocketName: pocketName,
          startDate: start.format("YYYY-MM-DD"),
          endDate: end.format("YYYY-MM-DD"),
          interval: "1d",
        },
      });
      if (Object.keys(res.data).length !== 0) {
        const date = res.data.date.map((date) => date.slice(0, 10));
        const mergedAssetVectors = mergeWithObject(date, res.data.assets);
        const mergedAssetClassVectors = mergeWithObject(
          date,
          res.data.asset_classes
        );

        delete res.data.date;
        delete res.data.assets;
        delete res.data.asset_classes;

        const mergedPocketVectors = mergeWithObject(date, res.data);

        setPocketVectors(mergedPocketVectors);
        setAssetVectors(mergedAssetVectors);
        setAssetClassVectors(mergedAssetClassVectors);
      } else {
        setPocketVectors({});
        setAssetVectors({});
        setAssetClassVectors({});
      }
    } catch (err) {
      alert(err.response.data.error.message);
    } finally {
      setIsDataLoading(false);
    }
  };

  const merge = (data) => {
    return data.map((item) => ({
      name: item.asset.ticker,
      value: parseFloat(parseFloat(item.participation).toFixed(1)),
    }));
  };

  const assetDataKeys = assetVectors[0]
    ? Object.keys(assetVectors[0]).filter((key) => key !== "date")
    : [];

  const assetClassDataKeys = assetClassVectors[0]
    ? Object.keys(assetClassVectors[0]).filter((key) => key !== "date")
    : [];

  React.useEffect(() => {
    const fetchData = async () => {
      await Promise.all([
        getPocketDetail(),
        getPocketVectors(startDate, endDate),
      ]);
    };
    fetchData();
  }, []);

  const toggleDrawer = () => {
    setOpen(!open);
  };

  return (
    <ThemeProvider theme={defaultTheme}>
      <Box sx={{ display: "flex" }}>
        <CssBaseline />
        <AppBar open={open} toggleDrawer={toggleDrawer} />
        <SideBar open={open} toggleDrawer={toggleDrawer} />
        <PageContainer>
          <Grid container>
            <Grid item xs={12} sx={{ height: "20px" }}></Grid>
            <Grid item xs={1}>
              <Button
                variant="contained"
                size="medium"
                onClick={() =>
                  navigate(`${location.pathname.replace(/\/charts$/, "")}`)
                }
              >
                Outcomes
              </Button>
            </Grid>
            <Grid item xs={1}>
              <Button variant="contained" size="medium" disabled>
                Charts
              </Button>
            </Grid>
            <Grid item xs={1}>
              <Button
                variant="contained"
                size="medium"
                onClick={() =>
                  navigate(
                    `${location.pathname.replace(/\/charts$/, "")}` + "/history"
                  )
                }
              >
                History
              </Button>
            </Grid>
          </Grid>
          <Grid item xs={12} sx={{ height: "30px" }}></Grid>

          <DateRangePicker
            initialStartDate={startDate}
            initialEndDate={endDate}
            onDateChange={handleDateChange}
          />

          {isDataLoading ? (
            <CircularProgress />
          ) : (
            <Grid container spacing={2} rowSpacing={1}>
              <Grid item xs={12} sm={6}>
                <Paper sx={{ p: 2, display: "flex", flexDirection: "column" }}>
                  <React.Fragment>
                    <Title>Portfolio division</Title>
                    <GraphBlock type="pie" data={participationSeries} />
                  </React.Fragment>
                </Paper>
              </Grid>

              <Grid item xs={12} sm={6}>
                <Paper sx={{ p: 2, display: "flex", flexDirection: "column" }}>
                  <React.Fragment>
                    <Title>Portfolio stack over time</Title>
                    <GraphBlock
                      type="area"
                      data={assetVectors}
                      dataKey={assetDataKeys}
                    />
                  </React.Fragment>
                </Paper>
              </Grid>

              <Grid item xs={12} sm={6}>
                <Paper sx={{ p: 2, display: "flex", flexDirection: "column" }}>
                  <React.Fragment>
                    <Title>Portfolio asset class over time</Title>
                    <GraphBlock
                      type="area"
                      data={assetClassVectors}
                      dataKey={assetClassDataKeys}
                    />
                  </React.Fragment>
                </Paper>
              </Grid>

              <Grid item xs={12} sm={6}>
                <Paper sx={{ p: 2, display: "flex", flexDirection: "column" }}>
                  <React.Fragment>
                    <Title>Portfolio net deposit value</Title>
                    <GraphBlock
                      type="line"
                      data={pocketVectors}
                      dataKey={"net_deposits_vector"}
                    />
                  </React.Fragment>
                </Paper>
              </Grid>

              <Grid item xs={12} sm={6}>
                <Paper sx={{ p: 2, display: "flex", flexDirection: "column" }}>
                  <React.Fragment>
                    <Title>Portfolio transaction cost</Title>
                    <GraphBlock
                      type="line"
                      data={pocketVectors}
                      dataKey={"transaction_cost_vector"}
                    />
                  </React.Fragment>
                </Paper>
              </Grid>

              <Grid item xs={12} sm={6}>
                <Paper sx={{ p: 2, display: "flex", flexDirection: "column" }}>
                  <React.Fragment>
                    <Title>Portfolio profit</Title>
                    <GraphBlock
                      type="line"
                      data={pocketVectors}
                      dataKey={"profit_vector"}
                    />
                  </React.Fragment>
                </Paper>
              </Grid>

              <Grid item xs={12} sm={6}>
                <Paper sx={{ p: 2, display: "flex", flexDirection: "column" }}>
                  <React.Fragment>
                    <Title>Free cash</Title>
                    <GraphBlock
                      type="line"
                      data={pocketVectors}
                      dataKey={"free_cash_vector"}
                    />
                  </React.Fragment>
                </Paper>
              </Grid>

              <Grid item xs={12} sm={6}>
                <Paper sx={{ p: 2, display: "flex", flexDirection: "column" }}>
                  <React.Fragment>
                    <Title>Portfolio value</Title>
                    <GraphBlock
                      type="line"
                      data={pocketVectors}
                      dataKey={"pocket_value_vector"}
                    />
                  </React.Fragment>
                </Paper>
              </Grid>

              <Grid item xs={12} sm={6}>
                <Paper sx={{ p: 2, display: "flex", flexDirection: "column" }}>
                  <React.Fragment>
                    <Title>Heatmap</Title>
                  </React.Fragment>
                </Paper>
              </Grid>
            </Grid>
          )}
        </PageContainer>
      </Box>
    </ThemeProvider>
  );
}
