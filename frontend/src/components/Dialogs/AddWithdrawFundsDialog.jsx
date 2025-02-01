import * as React from "react";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogContentText from "@mui/material/DialogContentText";
import DialogTitle from "@mui/material/DialogTitle";
import TextField from "@mui/material/TextField";
import Select from "@mui/material/Select";
import MenuItem from "@mui/material/MenuItem";
import FormControl from "@mui/material/FormControl";
import InputLabel from "@mui/material/InputLabel";
import Grid from "@mui/material/Grid";
import { Typography } from "@mui/material";

import api from "../../api";

export default function AddWithdrawFundsDialog(props) {
  const { open, onClose, pocket, addFunds, withdraw } = props;
  const [title, setTitle] = React.useState("");
  const [formValues, setFormValues] = React.useState({
    operation_type: title + "_funds",
    asset_class: null,
    ticker: null,
    date: new Date().toISOString().split("T")[0],
    currency: null,
    purchase_currency_price: null,
    quantity: "",
    price: null,
    fee: 0.0,
    comment: "",
    pocket_name: pocket ? pocket.name : "",
  });
  
  const process = (e) => {
    api
      .post("api/operations/", formValues)
      .then((res) => {
        if (res.status === 201) alert(title + " funds successfully");
        else alert("Error " + title + " funds");
      })
      .catch((err) => alert(err.response.data.error));
  };



  const handleChange = (event) => {
    const { name, value } = event.target;
    const numValue = !isNaN(value) ? parseFloat(value) : value;
    setFormValues({
      ...formValues,
      [name]: numValue,
    });
  };

  const handleSubmit = (event) => {
    formValues["pocket_name"] = pocket.name;
    formValues["operation_type"] = title + "_funds";
    event.preventDefault();
    process(event);
    onClose();
    
  };

  React.useEffect(() => {
    if (addFunds) {
      setTitle("add");
    } else if (withdraw) {
      setTitle("withdraw");
    } else {
      setTitle(""); // Domyślna wartość, jeśli żaden z warunków nie jest spełniony
    }
  }, [addFunds, withdraw]); // useEffect będzie wywoływany za każdym razem, gdy `addFunds` lub `withdraw` się zmieni


  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs">
      <DialogTitle>{title.charAt(0).toUpperCase() + title.slice(1)} funds</DialogTitle>
      <DialogContent>
        <Box component="form" onSubmit={handleSubmit} autoComplete="off">
          <Grid container spacing={2}>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Quantity"
                name="quantity"
                type="number"
                onChange={handleChange}
                required
                size="small"
                inputProps={{
                  min: 0.001,
                  step: 0.001,
                }}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                disabled
                label={pocket?.currency?.name || ""}
                size="small"
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Date"
                name="date"
                type="date"
                defaultValue={new Date().toISOString().split("T")[0]}
                onChange={handleChange}
                required
                size="small"
                InputLabelProps={{ shrink: true }}
              />
            </Grid>

            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Fee"
                name="fee"
                type="number"
                onChange={handleChange}
                size="small"
                inputProps={{
                  min: 0.001,
                  step: 0.001,
                }}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Comment"
                name="comment"
                defaultValue=""
                onChange={handleChange}
                size="small"
              />
            </Grid>
          </Grid>
          <DialogActions>
            <Button onClick={onClose}>Cancel</Button>
            <Button type="submit">{title}</Button>
          </DialogActions>
        </Box>
      </DialogContent>
    </Dialog>
  );
}
