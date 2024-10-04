import * as React from "react";
import { useParams } from "react-router-dom";
import { styled, createTheme, ThemeProvider } from "@mui/material/styles";
import CssBaseline from "@mui/material/CssBaseline";
import Box from "@mui/material/Box";
import Grid from "@mui/material/Grid";
import Paper from "@mui/material/Paper";
import Link from "@mui/material/Link";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import Toolbar from "@mui/material/Toolbar";
import { useNavigate, useLocation } from "react-router-dom";

import api from "../api";
import SideBar from "../components/Bars/SideBar";
import AppBar from "../components/Bars/AppBar";
import PageContainer from "../components/PageContainer";
import Title from "../components/Title";
import { Button } from "@mui/material";
import { PieChart } from "@mui/x-charts/PieChart";
import Chart from "../components/Chart";

function preventDefault(event) {
  event.preventDefault();
}

export default function PocketCharts() {
  const navigate = useNavigate();
  const location = useLocation();
  const pocketName = useParams().slug;
  const defaultTheme = createTheme();
  const [open, setOpen] = React.useState(true);

  const [pocketDetail, setPocketDetail] = React.useState([]);
  const [pocketProfitOverTime, setPocketProfitOverTime] = React.useState([]);

  const getPocketDetail = () => {
    api
      .get("api/asset-allocations", {
      params: {
        pocket_name: pocketName
      }
    })
      .then((res) => res.data)
      .then((data) => {
        setPocketDetail(data);
      })
      .catch((err) => alert(err));
  };

  const getProfitOverTime = () => {
    api
      .get("/api/profit-data", {
        params: {
          pocketName: pocketName,
          startDate: "2023-07-22",
          endDate: "2024-07-22",
        },
      })
      .then((response) => {
        const _chartData = ({
          date: response.data.Date,
          value: response.data.Close,
        });
        setPocketProfitOverTime(_chartData);
      })
      .catch((error) => {
        console.error("Error fetching data:", error);
      });
  };

  const [loading, setLoading] = React.useState(true);

  // Effect for setting the charging state
  React.useEffect(() => {
    if (pocketProfitOverTime.value) {
      setLoading(false);
    } else {
      setLoading(true);
    }
  }, [pocketProfitOverTime]);

  const toggleDrawer = () => {
    setOpen(!open);
  };

  React.useEffect(() => {
    getPocketDetail();
    getProfitOverTime();
  }, []);

  const participationSeries = pocketDetail.map((row) => ({
    label: row.asset.name,
    value: row.participation,
  }));


  return (
    <ThemeProvider theme={defaultTheme}>
      <Box sx={{ display: "flex" }}>
        <CssBaseline />
        <AppBar open={open} toggleDrawer={toggleDrawer} />
        <SideBar open={open} toggleDrawer={toggleDrawer} />
        <PageContainer>
          <Grid item xs={2}>
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
          <Grid item xs={12}>
            <Paper sx={{ p: 2, display: "flex", flexDirection: "column" }}>
              <React.Fragment>
                <Title>Portfolio division</Title>
                <PieChart
                  series={[
                    {
                      data: participationSeries,
                      outerRadius: 150,
                      innerRadius: 60,
                      paddingAngle: 1,
                      cornerRadius: 5,
                    },
                  ]}
                  height={350}
                />
              </React.Fragment>
            </Paper>
            <div style={{ height: 10 }}></div>
            <Paper sx={{ p: 2, display: "flex", flexDirection: "column", height:400 }} >
              <React.Fragment>
                <Title>Rate of return</Title>
                <Chart x={pocketProfitOverTime.date} y={pocketProfitOverTime.value} loading={loading} />
                                
              </React.Fragment>
            </Paper>
            <div style={{ height: 10 }}></div>

            <Paper sx={{ p: 2, display: "flex", flexDirection: "column" }}>
              <React.Fragment>
                <Title>Heatmap</Title>
                
              </React.Fragment>
            </Paper>
            <div style={{ height: 10 }}></div>

            <Paper sx={{ p: 2, display: "flex", flexDirection: "column" }}>
              <React.Fragment>
                <Title>Chart</Title>
                
              </React.Fragment>
            </Paper>
            <div style={{ height: 10 }}></div>

            <Paper sx={{ p: 2, display: "flex", flexDirection: "column" }}>
              <React.Fragment>
                <Title>Chart</Title>
                
              </React.Fragment>
            </Paper>
          </Grid>
        </PageContainer>
      </Box>
    </ThemeProvider>
  );
}
