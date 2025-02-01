import * as React from "react";
import { useParams } from "react-router-dom";
import { styled, createTheme, ThemeProvider } from "@mui/material/styles";
import CssBaseline from "@mui/material/CssBaseline";
import Box from "@mui/material/Box";
import Grid from "@mui/material/Grid";
import Paper from "@mui/material/Paper";
import Link from "@mui/material/Link";
import CircularProgress from "@mui/material/CircularProgress";
import Typography from "@mui/material/Typography";

import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TableFooter,
} from "@mui/material";
import { Button } from "@mui/material";

import Toolbar from "@mui/material/Toolbar";
import { useNavigate, useLocation } from "react-router-dom";

import api from "../api";
import SideBar from "../components/Bars/SideBar";
import AppBar from "../components/Bars/AppBar";
import PageContainer from "../components/PageContainer";
import Title from "../components/Title";
import AddMenus from "../components/AddMenus";
import DataTable from "../components/DataTable";
import { cellStyle } from "../components/utils";

export default function PocketAssetsDetail() {
  const navigate = useNavigate();
  const location = useLocation();
  const pocketName = useParams().slug;
  const defaultTheme = createTheme();
  const [loading, setLoading] = React.useState(true);
  const [open, setOpen] = React.useState(true);
  const [menuDialogStates, setMenuDialogStates] = React.useState({
    buyDialogOpen: false,
    sellDialogOpen: false,
    addFundsDialogOpen: false,
    withdrawFundsDialogOpen: false,
  });
  const [pocketAssetAllocationDetail, setPocketAssetAllocationDetail] =
    React.useState([]);
  const [pocket, setPocket] = React.useState([]);

  const toggleDialogStates = (dialogName, open) => {
    setMenuDialogStates((prevState) => ({
      ...prevState,
      [dialogName]: open,
    }));
  };
  const getAssetAllocations = async () => {
    try {
      const res = await api.get("api/asset-allocations", {
        params: {
          pocket_name: pocketName,
        },
      });

      const transformedData = transformData(res.data);
      setPocketAssetAllocationDetail(transformedData);
    } catch (err) {
      alert(err.response.data.error.message);
    }
  };

  const getPocketDetail = async () => {
    try {
      const res = await api.get("api/pockets", {
        params: { name: pocketName },
      });
      setPocket(res.data[0]);
    } catch (err) {
      alert(err.response.data.error.message);
    }
  };

  const fetchData = async () => {
    setLoading(true);
    await Promise.all([getAssetAllocations(), getPocketDetail()]);
    setLoading(false);
  };

  const transformData = (data) => {
    return data.map((item) => {
      const id = item.id;
      const ticker = item.asset.ticker;
      const name = item.asset.name;
      const asset_class = item.asset.asset_class;
      const currency = item.asset.currency.name;
      const quantity = parseFloat(item.quantity);
      const average_purchase_currency_price = parseFloat(
        item.average_purchase_currency_price
      );
      const average_purchase_price = parseFloat(item.average_purchase_price);
      const current_price = parseFloat(item.asset.current_price);
      const daily_change_percent = parseFloat(item.daily_change_percent);
      const daily_change = parseFloat(item.daily_change_XXX);
      const participation = parseFloat(item.participation);
      const total_value = parseFloat(item.total_value_XXX);
      const rate_of_return_percent = parseFloat(item.rate_of_return);
      const rate_of_return_currency = parseFloat(item.rate_of_return_XXX);
      const profit = parseFloat(item.profit_XXX);

      // Zwrócenie nowej płaskiej struktury
      return {
        id,
        ticker,
        name,
        asset_class,
        currency,
        quantity,
        average_purchase_currency_price,
        average_purchase_price,
        current_price,
        daily_change_percent,
        daily_change,
        participation,
        total_value,
        rate_of_return_percent,
        rate_of_return_currency,
        profit,
      };
    });
  };

  const toggleDrawer = () => {
    setOpen(!open);
  };

  const columns = [
    {
      name: "id",
      label: "ID",
      options: {
        filter: true,
        sort: true,
        display: false,
      },
    },
    {
      name: "ticker",
      label: "Ticker",
      options: {
        filter: true,
        sort: true,
        display: false,
      },
    },
    {
      name: "name",
      label: "Name",
      options: {
        filter: true,
        sort: true,
      },
    },
    {
      name: "asset_class",
      label: "Asset Class",
      options: {
        filter: true,
        sort: true,
      },
    },
    {
      name: "currency",
      label: "Currency",
      options: {
        filter: true,
        sort: true,
      },
    },
    {
      name: "quantity",
      label: "Quantity",
      options: {
        filter: true,
        sort: true,
        customBodyRender: (value) => {
          value = Number(value.toFixed(2));
          return cellStyle(value);
        },
      },
    },
    {
      name: "average_purchase_currency_price",
      label: `Average purchase currency price [${pocket.currency?.name}]`,
      options: {
        filter: true,
        sort: true,
        customBodyRender: (value) => {
          value = Number(value.toFixed(2));
          return cellStyle(value);
        },
      },
    },
    {
      name: "average_purchase_price",
      label: `Average purchase price [${pocket.currency?.name}]`,
      options: {
        filter: true,
        sort: true,
        customBodyRender: (value) => {
          value = Number(value.toFixed(2));
          return cellStyle(value);
        },
      },
    },
    {
      name: "current_price",
      label: `Current price [${pocket.currency?.name}]`,
      options: {
        filter: true,
        sort: true,
        customBodyRender: (value) => {
          value = Number(value.toFixed(2));
          return cellStyle(value);
        },
      },
    },
    {
      name: "daily_change_percent",
      label: "Daily change %",
      options: {
        filter: true,
        sort: true,
        customBodyRender: (value) => {
          value = Number(value.toFixed(2));
          return cellStyle(value, true);
        },
      },
    },
    {
      name: "daily_change",
      label: `Daily change [${pocket.currency?.name}]`,
      options: {
        filter: true,
        sort: true,
        customBodyRender: (value) => {
          value = Number(value.toFixed(2));
          return cellStyle(value, true);
        },
      },
    },
    {
      name: "participation",
      label: "Participation in portfolio",
      options: {
        filter: true,
        sort: true,
        customBodyRender: (value) => {
          return value.toFixed(1);
        },
      },
    },
    {
      name: "total_value",
      label: `Total value [${pocket.currency?.name}]`,
      options: {
        filter: true,
        sort: true,
        customBodyRender: (value) => {
          value = Number(value.toFixed(1));
          return cellStyle(value);
        },
      },
    },
    {
      name: "rate_of_return_percent",
      label: "Rate of return %",
      options: {
        filter: true,
        sort: true,
        customBodyRender: (value) => {
          value = Number(value.toFixed(1));
          return cellStyle(value, true);
        },
      },
    },
    {
      name: "rate_of_return_currency",
      label: `Rate of return % [${pocket.currency?.name}]`,
      options: {
        filter: true,
        sort: true,
        customBodyRender: (value) => {
          value = Number(value.toFixed(1));
          return cellStyle(value, true);
        },
      },
    },
    {
      name: "profit",
      label: `Profit [${pocket.currency?.name}]`,
      options: {
        filter: true,
        sort: true,
        customBodyRender: (value) => {
          value = Number(value.toFixed(2));
          return cellStyle(value, true);
        },
      },
    },
  ];

  const options = {
    filter: true,
    selectableRows: "none",
    expandableRows: true,
    rowsPerPageOptions: [10, 20, 50, 100],

    setTableProps: () => ({
      // size: 'small',
      stickyHeader: true,
      padding: "none",
    }),

    renderExpandableRow: (rowData, rowMeta) => {
      return (
        <tr>
          <td colSpan={4}>
            <TableContainer>
              <Table style={{ margin: "0 auto" }}>
                <TableHead>
                  <TableCell align="right">Name</TableCell>
                  <TableCell align="right">Color</TableCell>
                </TableHead>
                <TableBody>
                  <TableRow>
                    <TableCell component="th" scope="row" align="right">
                      ABXD
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </TableContainer>
          </td>
        </tr>
      );
    },

    customTableBodyFooterRender: (opts) => {
      const theme = createTheme({
        components: {
          MuiTableCell: {
            styleOverrides: {
              root: {
                textAlign: "center",
                verticalAlign: "middle",
                fontWeight: "bolder",
                fontSize: 14,
              },
            },
          },
          MuiTableFooter: {
            styleOverrides: {
              root: {
                backgroundColor: "#f5f5dc", // Kolor beżowy
              },
            },
          },
        },
      });

      let sumDailyChange = opts.data?.reduce((acc, item) => {
        return acc + item.data[10].props.children;
      }, 0);

      let sumTotalValue = opts.data?.reduce((acc, item) => {
        return acc + item.data[12].props.children;
      }, 0);

      let sumDailyChangePercent = (sumDailyChange / sumTotalValue) * 100;

      let sumProfit = opts.data?.reduce((acc, item) => {
        return acc + item.data[15].props.children;
      }, 0);

      let totalValue = opts.data?.reduce((acc, item) => {
        return acc + item.data[5].props.children * item.data[8].props.children;
      }, 0);
      let totalCostCurrency = opts.data?.reduce((acc, item) => {
        return acc + item.data[5].props.children * item.data[7].props.children;
      }, 0);

      let portfolioRateOfReturn =
        ((totalValue - totalCostCurrency) / totalCostCurrency) * 100;
      let portfolioRateOfReturnCurrency =
        (sumProfit / (sumTotalValue - sumProfit)) * 100;

      return (
        <>
          <ThemeProvider theme={theme}>
            <TableFooter>
              <TableRow>
                <TableCell />
                {opts.columns.map((col, index) => {
                  if (col.display === "true") {
                    if (col.name === "id") {
                      return <TableCell key={index}></TableCell>;
                    } else if (col.name === "ticker") {
                      return <TableCell key={index}></TableCell>;
                    } else if (col.name === "name") {
                      return <TableCell key={index}>Total</TableCell>;
                    } else if (col.name === "asset_class") {
                      return <TableCell key={index}></TableCell>;
                    } else if (col.name === "currency") {
                      return <TableCell key={index}></TableCell>;
                    } else if (col.name === "quantity") {
                      return <TableCell key={index}></TableCell>;
                    } else if (col.name === "average_purchase_currency_price") {
                      return <TableCell key={index}></TableCell>;
                    } else if (col.name === "average_purchase_price") {
                      return <TableCell key={index}></TableCell>;
                    } else if (col.name === "current_price") {
                      return <TableCell key={index}></TableCell>;
                    } else if (col.name === "daily_change_percent") {
                      return (
                        <TableCell key={index}>
                          {sumDailyChangePercent.toFixed(2)}
                        </TableCell>
                      );
                    } else if (col.name === "daily_change") {
                      return (
                        <TableCell key={index}>
                          {sumDailyChange.toFixed(2)}
                        </TableCell>
                      );
                    } else if (col.name === "participation") {
                      return <TableCell key={index}></TableCell>;
                    } else if (col.name === "total_value") {
                      return (
                        <TableCell key={index}>
                          {sumTotalValue.toFixed(1)}
                        </TableCell>
                      );
                    } else if (col.name === "rate_of_return_percent") {
                      return (
                        <TableCell key={index}>
                          {portfolioRateOfReturn.toFixed(1)}
                        </TableCell>
                      );
                    } else if (col.name === "rate_of_return_currency") {
                      return (
                        <TableCell key={index}>
                          {portfolioRateOfReturnCurrency.toFixed(1)}
                        </TableCell>
                      );
                    } else if (col.name === "profit") {
                      return (
                        <TableCell key={index}>
                          {sumProfit.toFixed(1)}
                        </TableCell>
                      );
                    }
                  }
                })}
              </TableRow>
            </TableFooter>
          </ThemeProvider>
        </>
      );
    },
  };

  React.useEffect(() => {
    fetchData();
  }, []);

  React.useEffect(() => {
    const fetchData = async () => {
      if (!menuDialogStates.buyDialogOpen) {
        await getAssetAllocations();
        await getPocketDetail();
      }
    };
    fetchData();
  }, [menuDialogStates.buyDialogOpen]);

  React.useEffect(() => {
    const fetchData = async () => {
      if (!menuDialogStates.sellDialogOpen) {
        await getAssetAllocations();
        await getPocketDetail();
      }
    };
    fetchData();
  }, [menuDialogStates.sellDialogOpen]);

  React.useEffect(() => {
    const fetchData = async () => {
      if (!menuDialogStates.addFundsDialogOpen) {
        await getPocketDetail();
      }
    };
    fetchData();
  }, [menuDialogStates.addFundsDialogOpen]);

  React.useEffect(() => {
    const fetchData = async () => {
      if (!menuDialogStates.withdrawFundsDialogOpen) {
        await getPocketDetail();
      }
    };
    fetchData();
  }, [menuDialogStates.withdrawFundsDialogOpen]);

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
              <AddMenus
                pocket={pocket}
                pocketAssetAllocationDetail={pocketAssetAllocationDetail}
                menuDialogStates={menuDialogStates}
                toggleDialogStates={toggleDialogStates}
              />
            </Grid>
            <Grid item xs={1}>
              <Button
                variant="contained"
                size="medium"
                onClick={() => navigate(`${location.pathname}/charts`)}
              >
                Charts
              </Button>
            </Grid>
            <Grid item xs={1}>
              <Button
                variant="contained"
                size="medium"
                onClick={() => navigate(`${location.pathname}/history`)}
              >
                History
              </Button>
            </Grid>
          </Grid>

          <Grid item xs={12} sx={{ height: "30px" }}></Grid>
          <Box sx={{ position: "relative", width: "100%" }}>
            <Grid container>
              <Grid item xs={12}>
                {loading ? ( // Sprawdzamy, czy dane są ładowane
                  <Box
                    sx={{
                      display: "flex",
                      justifyContent: "center",
                      alignItems: "center",
                      height: "200px",
                    }}
                  >
                    <CircularProgress />
                  </Box>
                ) : (
                  <DataTable
                    title={"Pocket Composition"}
                    options={options}
                    columns={columns}
                    data={
                      pocketAssetAllocationDetail
                        ? pocketAssetAllocationDetail
                        : []
                    }
                  />
                )}
              </Grid>
            </Grid>
            <Box
              sx={{
                position: "absolute",
                bottom: "0px",
                left: "0",
                zIndex: 1,
              }}
            >
              {!loading ? (
                pocket.currency && (
                  <Paper
                    elevation={0}
                    sx={{
                      p: 1.78,
                      display: "flex",
                      alignItems: "center",
                    }}
                  >
                    <Typography>Free Cash:</Typography>
                    <Typography
                      variant="body1"
                      sx={{ fontWeight: 500, color: "#1976d2", ml: 2 }}
                    >
                      {`${Number(pocket.free_cash).toFixed(2)} ${
                        pocket.currency.name
                      }`}
                    </Typography>
                  </Paper>
                )
              ) : (
                <></>
              )}
            </Box>
          </Box>
        </PageContainer>
      </Box>
    </ThemeProvider>
  );
}
