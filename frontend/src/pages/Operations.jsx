import * as React from "react";
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
import { Button, IconButton } from "@mui/material";

import SideBar from "../components/Bars/SideBar";
import AppBar from "../components/Bars/AppBar";
import api from "../api";
import PageContainer from "../components/PageContainer";
import DataTable from "../components/DataTable";
import Title from "../components/Title";
import { cellStyle } from "../components/utils";

function preventDefault(event) {
  event.preventDefault();
}

export default function Operations() {
  const defaultTheme = createTheme();
  const [open, setOpen] = React.useState(true);
  const [operations, setOperations] = React.useState([]);
  const toggleDrawer = () => {
    setOpen(!open);
  };

  const getOperations = async () => {
    try {
      const res = await api.get("api/operations", {
      });
      setOperations(res.data);
    } catch (err) {
      alert(err.response.data.error);
    }
  };



  React.useEffect(() => {
    const fetchData = async () => {
      await Promise.all([getOperations()]);
    };
    fetchData();
  }, []);


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
      name: "date",
      label: "Date",
      options: {
        filter: true,
        sort: true,
      },
    },
    {
      name: "pocket_name",
      label: "Pocket",
      options: {
        filter: true,
        sort: true,
      },
    },
    {
      name: "operation_type",
      label: "Operation",
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
      name: "ticker",
      label: "Ticker",
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
          value.toFixed(2);
          return cellStyle(value);
        },
      },
    },
    {
      name: "price",
      label: "Price",
      options: {
        filter: true,
        sort: true,
        customBodyRender: (value) => {
          value?.toFixed(2);
          return cellStyle(value);
        },
      },
    },
    {
      name: "fee",
      label: "Fee",
      options: {
        filter: true,
        sort: true,
        customBodyRender: (value) => {
          value.toFixed(1);
          return cellStyle(value);
        },
      },
    },
    {
      name: "delete",
      label: "Delete",
      options: {
        viewColumns: false,
        filter: false,
        customBodyRender: (value, tableMeta) => {
          return (
            <div>
              <Button
                onClick={() => {
                  handleClickDelete(tableMeta.rowData[0]);
                }}
              >
                {" "}
                Delete
              </Button>
            </div>
          );
        },
      },
    },
  ];

  const options = {
    filter: true,
    selectableRows: "none",
    expandableRows: true,
    rowsPerPageOptions: [20, 50, 100],
    rowsPerPage: 20,

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
  };

  return (
    <ThemeProvider theme={defaultTheme}>
      <Box sx={{ display: "flex" }}>
        <CssBaseline />
        <AppBar open={open} toggleDrawer={toggleDrawer} />
        <SideBar open={open} toggleDrawer={toggleDrawer} />
        <PageContainer>
          <Grid container>
          <Grid item xs={12} sx={{ height: "30px" }}></Grid>
            <Grid item xs={12}>
              <DataTable
                title={"Operation History"}
                options={options}
                columns={columns}
                data={operations ? operations : []}
              />
            </Grid>
          </Grid>
        </PageContainer>
      </Box>
    </ThemeProvider>
  );
}
