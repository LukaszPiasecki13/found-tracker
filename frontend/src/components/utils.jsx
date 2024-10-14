import React from "react";
/**
 * 
 * @param {number} value 
 * @param {boolean} isCollored 
 * @returns {JSX.Element}
 */

export const cellStyle = (value, isCollored = false) => {
    if (isCollored) {
      if (value < 0) {
        return <div style={{ color: "red" }}>{value}</div>;
      } else if (value > 0) {
        return <div style={{ color: "green" }}>{value}</div>;
      }
    } else {
      return <div style={{ color: "black" }}>{value}</div>;
    }
  };