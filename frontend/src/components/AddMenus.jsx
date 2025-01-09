import * as React from "react";
import { styled, alpha } from "@mui/material/styles";
import Button from "@mui/material/Button";
import Menu from "@mui/material/Menu";
import MenuItem from "@mui/material/MenuItem";
import EditIcon from "@mui/icons-material/Edit";
import Divider from "@mui/material/Divider";
import ArchiveIcon from "@mui/icons-material/Archive";
import FileCopyIcon from "@mui/icons-material/FileCopy";
import MoreHorizIcon from "@mui/icons-material/MoreHoriz";
import KeyboardArrowDownIcon from "@mui/icons-material/KeyboardArrowDown";

import BuyDialog from "./Dialogs/BuyDialog";
import SellDialog from "./Dialogs/SellDialog";
import AddWithdrawFundsDialog from "./Dialogs/AddWithdrawFundsDialog";

const StyledMenu = styled((props) => (
  <Menu
    elevation={0}
    anchorOrigin={{
      vertical: "bottom",
      horizontal: "right",
    }}
    transformOrigin={{
      vertical: "top",
      horizontal: "right",
    }}
    {...props}
  />
))(({ theme }) => ({
  "& .MuiPaper-root": {
    borderRadius: 6,
    marginTop: theme.spacing(1),
    minWidth: 180,
    color:
      theme.palette.mode === "light"
        ? "rgb(55, 65, 81)"
        : theme.palette.grey[300],
    boxShadow:
      "rgb(255, 255, 255) 0px 0px 0px 0px, rgba(0, 0, 0, 0.05) 0px 0px 0px 1px, rgba(0, 0, 0, 0.1) 0px 10px 15px -3px, rgba(0, 0, 0, 0.05) 0px 4px 6px -2px",
    "& .MuiMenu-list": {
      padding: "4px 0",
    },
    "& .MuiMenuItem-root": {
      "& .MuiSvgIcon-root": {
        fontSize: 18,
        color: theme.palette.text.secondary,
        marginRight: theme.spacing(1.5),
      },
      "&:active": {
        backgroundColor: alpha(
          theme.palette.primary.main,
          theme.palette.action.selectedOpacity
        ),
      },
    },
  },
}));

export default function AddMenus(props) {
  const { menuDialogStates, toggleDialogStates } = props;
  const pocket = props.pocket;
  const [anchorEl, setAnchorEl] = React.useState(null);

  const open = Boolean(anchorEl);
  const handleClick = (event) => {
    setAnchorEl(event.currentTarget);
  };
  const handleClose = () => {
    setAnchorEl(null);
  };

  return (
    <div>
      <Button
        id="demo-customized-button"
        aria-controls={open ? "demo-customized-menu" : undefined}
        aria-haspopup="true"
        aria-expanded={open ? "true" : undefined}
        variant="contained"
        disableElevation
        onClick={handleClick}
        endIcon={<KeyboardArrowDownIcon />}
      >
        Add
      </Button>
      <StyledMenu
        id="demo-customized-menu"
        MenuListProps={{
          "aria-labelledby": "demo-customized-button",
        }}
        anchorEl={anchorEl}
        open={open}
        onClose={handleClose}
      >
        <MenuItem
          onClick={() => {
            handleClose();
            toggleDialogStates("buyDialogOpen", true);
          }}
          disableRipple
        >
          Buy
        </MenuItem>
        <MenuItem
          onClick={() => {
            handleClose();
            toggleDialogStates("sellDialogOpen", true);
          }}
          disableRipple
        >
          Sell
        </MenuItem>
        <Divider sx={{ my: 0.5 }} />
        <MenuItem
          onClick={() => {
            handleClose();
            toggleDialogStates("addFundsDialogOpen", true);
          }}
          disableRipple
        >
          Add funds
        </MenuItem>
        <MenuItem
          onClick={() => {
            handleClose();
            toggleDialogStates("withdrawFundsDialogOpen", true);
          }}
          disableRipple
        >
          Withdraw funds
        </MenuItem>
      </StyledMenu>
      <BuyDialog
        open={menuDialogStates.buyDialogOpen}
        onClose={() => {
          toggleDialogStates("buyDialogOpen", false);
        }}
        pocket={pocket}
      />
      <SellDialog
        open={menuDialogStates.sellDialogOpen}
        onClose={() => {
          toggleDialogStates("sellDialogOpen", false);
        }}
        pocket={pocket}
        pocketAssetAllocationDetail={props.pocketAssetAllocationDetail}
      />
      <AddWithdrawFundsDialog
        open={
          menuDialogStates.addFundsDialogOpen ||
          menuDialogStates.withdrawFundsDialogOpen
        }
        onClose={() => {
          toggleDialogStates("addFundsDialogOpen", false);
          toggleDialogStates("withdrawFundsDialogOpen", false);
        }}
        pocket={pocket}
        addFunds={menuDialogStates.addFundsDialogOpen}
        withdraw={menuDialogStates.withdrawFundsDialogOpen}
      />
    </div>
  );
}
