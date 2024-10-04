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
import SideBar from "../components/Bars/SideBar";
import AppBar from "../components/Bars/AppBar";
import api from "../api";
import PageContainer from "../components/PageContainer";

import Title from "../components/Title";

function preventDefault(event) {
  event.preventDefault();
}

export default function Operations() {
  const defaultTheme = createTheme();
  const [open, setOpen] = React.useState(true);
  const toggleDrawer = () => {
    setOpen(!open);
  };

  React.useEffect(() => {
    getOperations();
  }, []);

  const [operations, setOperations] = React.useState([]);

  const getOperations = () => {
    api
      .get("api/operations")
      .then((res) => res.data)
      .then((data) => setOperations(data))
      .catch((err) => alert(err));
  };

  return (
    <ThemeProvider theme={defaultTheme}>
      <Box sx={{ display: "flex" }}>
        <CssBaseline />
        <AppBar open={open} toggleDrawer={toggleDrawer} />
        <SideBar open={open} toggleDrawer={toggleDrawer} />

        <PageContainer>
          <Grid item xs={12}>
            <Paper sx={{ p: 2, display: "flex", flexDirection: "column" }}>
              <React.Fragment>
                <Title>Operation History</Title>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Date</TableCell>
                      <TableCell>Pocket</TableCell>
                      <TableCell>Operation</TableCell>
                      <TableCell>Asset Class</TableCell>
                      <TableCell>Name</TableCell>
                      <TableCell>Ticker</TableCell>
                      <TableCell>Currency</TableCell>
                      <TableCell>Quantity</TableCell>
                      <TableCell>Price</TableCell>
                      <TableCell align="right">Fee</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {operations.map((row) => (
                      <TableRow key={row.id}>
                        <TableCell>{row.date}</TableCell>
                        <TableCell>{row.pocket_name}</TableCell>
                        <TableCell>{row.operation_type}</TableCell>
                        <TableCell>{row.asset_class}</TableCell>
                        <TableCell>name</TableCell>
                        <TableCell>{row.ticker}</TableCell>
                        <TableCell>{row.currency}</TableCell>
                        <TableCell>{row.quantity}</TableCell>
                        <TableCell>{row.price}</TableCell>
                        <TableCell align="right">{`$${row.fee}`}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
                <Link
                  color="primary"
                  href="#"
                  onClick={preventDefault}
                  sx={{ mt: 3 }}
                >
                  See more
                </Link>
              </React.Fragment>
            </Paper>
          </Grid>
        </PageContainer>
      </Box>
    </ThemeProvider>
  );
}
