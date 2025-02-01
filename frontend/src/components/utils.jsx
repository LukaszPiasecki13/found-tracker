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

export const mergeWithObject = (date, object) => {
  const dataArray = [];
  for (let i = 0; i < date.length; i++) {
    const dataPoint = {
      date: date[i],
    };

    for (const element in object) {
      if (object.hasOwnProperty(element)) {
        dataPoint[element] = object[element][i].toFixed(1);
      }
    }

    dataArray.push(dataPoint);
  }
  return dataArray;
};
