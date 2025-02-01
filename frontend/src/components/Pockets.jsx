import * as React from "react";
import { useNavigate } from "react-router-dom";
import {
  Box,
  IconButton,
  ListItemButton,
  ListItemIcon,
  ListItemText,
} from "@mui/material";
import { Add, Delete } from "@mui/icons-material";

import api from "../api";
import Title from "./Title";
import AddPocketDialog from "./Dialogs/AddPocketDialog";

export default function Pockets() {
  const navigate = useNavigate();
  const [pockets, setPockets] = React.useState([]);
  const [pocketAddDialogOpen, setPocketAddDialogOpen] = React.useState(false);

  const getPockets = async () => {
    try {
      const response = await api.get("api/pockets/");
      setPockets(response.data);
    } catch (error) {
      alert(err.response.data.error.message);
    }
  };

  const deletePocket = async (id) => {
    try {
      await api.delete("api/pockets/" + id);
      setPockets(pockets.filter((pocket) => pocket.id !== id));
    } catch (error) {
      alert(err.response.data.error.message);
    }
  };

  React.useEffect(() => {
    getPockets();
  }, []);

  return (
    <React.Fragment>
      <Box display="flex" justifyContent="space-between" alignItems="center">
        <Title>Pockets</Title>
        <IconButton
          color="primary"
          onClick={() => setPocketAddDialogOpen(true)}
        >
          <Add />
        </IconButton>
      </Box>
      {pockets.map((pocket) => (
        <ListItemButton
          key={pocket.id}
          onClick={() => navigate("/pockets/" + pocket.name)}
        >
          <ListItemIcon></ListItemIcon>
          <ListItemText primary={pocket.name} />
          <IconButton
            edge="end"
            aria-label="delete"
            onClick={(event) => {
              event.stopPropagation();
              deletePocket(pocket.id);
            }}
          >
            <Delete />
          </IconButton>
        </ListItemButton>
      ))}

      <AddPocketDialog
        open={pocketAddDialogOpen}
        onClose={() => {
          setPocketAddDialogOpen(false);
        }}
        setPockets={setPockets}
      />
    </React.Fragment>
  );
}
