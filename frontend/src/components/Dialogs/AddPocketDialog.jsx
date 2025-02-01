import * as React from "react";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import TextField from "@mui/material/TextField";
import Grid from "@mui/material/Grid";
import { FormControl } from "@mui/material";
import InputLabel from "@mui/material/InputLabel";
import Select from "@mui/material/Select";
import MenuItem from "@mui/material/MenuItem";

import api from "../../api";

export default function AddPocketDialog(props) {
  const { open, onClose, setPockets } = props;
  const [currencies, setCurrencies] = React.useState([]);
  const [formValues, setFormValues] = React.useState({
    name: "",
    currency: null,
  });

  const getCurrencies = async () => {
    try {
      const response = await api.get("api/currencies/");
      await setCurrencies(response.data);
    } catch (error) {
      alert(error.response.data.error.message);
    }
  };

  const process = async () => {
    try {
      const response = await api.post("api/pockets/", formValues);
      setPockets((prevPockets) => [...prevPockets, response.data]);
    } catch (err) {
      alert(err.response.data.error.message);
    }
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
    event.preventDefault();
    process(event);
    onClose();
  };

  React.useEffect(() => {
    getCurrencies();
  }, []);

  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs">
      <DialogTitle>Add Pocket</DialogTitle>
      <DialogContent>
        <Box component="form" onSubmit={handleSubmit} autoComplete="off">
          <Grid container spacing={2}>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Name"
                name="name"
                defaultValue=""
                onChange={handleChange}
                size="small"
                required
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <FormControl fullWidth size="small" required>
                <InputLabel id="currency-label">Currency</InputLabel>
                <Select
                  labelId="currency-label"
                  name="currency"
                  onChange={handleChange}
                >
                  {currencies
                    ? currencies.map((currency) => (
                        <MenuItem key={currency.name} value={currency.id}>
                          {currency.name}
                        </MenuItem>
                      ))
                    : null}
                </Select>
              </FormControl>
            </Grid>
          </Grid>
          <DialogActions>
            <Button onClick={onClose}>Cancel</Button>
            <Button type="submit">Add</Button>
          </DialogActions>
        </Box>
      </DialogContent>
    </Dialog>
  );
}
