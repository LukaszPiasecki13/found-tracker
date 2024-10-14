import * as React from "react";

import CircularProgress from "@mui/material/CircularProgress";
import PropTypes from "prop-types";
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  Pie,
  PieChart,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { scaleOrdinal } from "d3-scale";
import { schemeCategory10 } from "d3-scale-chromatic";

const generateColors = (numColors) => {
  const scale = scaleOrdinal(schemeCategory10);
  return Array.from({ length: numColors }, (_, i) => scale(i));
};

export default function GraphBlock({
  type,
  data,
  dataKey,
  width = 600,
  height = 300,
}) {

  const numberOfColors = () => {
    if (type === "pie") {
      return data.length;
    } else {
      return Array.isArray(dataKey) ? dataKey.length : 1;
    }
  };

  const colors = generateColors(numberOfColors());

  // const [activeKey, setActiveKey] = React.useState(null); // Stan do trzymania aktywnego dataKey

  // // Funkcja dla dynamicznego renderowania wykresu
  // const handleMouseEnter = (key) => {
  //   setActiveKey(key);  // Ustawia aktywny wykres
  // };

  // const handleMouseLeave = () => {
  //   setActiveKey(null);  // Resetuje aktywny wykres
  // };

  if (data.length == 0) {
    return <CircularProgress />;
  } else {
    switch (type) {
      case "pie":
        return (
          <ResponsiveContainer width="100%" height={height}>
            <PieChart width={width} height={height}>
              <Tooltip />
              <Legend />
              <Pie
                data={data}
                dataKey="value"
                // nameKey="label"
                cx="50%"
                cy="50%"
                outerRadius={100}
                fill="#82ca9d"
                isAnimationActive={false}
              >
                {data.map((entry, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={colors[index % colors.length]}
                  />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
        );
      case "line":
        return (
          <ResponsiveContainer width="100%" height={height}>
            <LineChart
              width={width}
              height={height}
              data={data}
              margin={{ left: 10, right: 10, bottom: 30 }}
            >
              <CartesianGrid strokeDasharray="1 1" strokeOpacity={0.9} />
              <XAxis
                dataKey="date"
                tick={{ angle: -60, dy: 20, fontSize: 12 }}
              />
              <YAxis dataKey={dataKey} />
              <Tooltip isAnimationActive={false} />
              <Legend verticalAlign="top" />
              <Line
                dataKey={dataKey}
                stroke="#82ca9d"
                dot={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        );
      case "bar":
        return (
          <ResponsiveContainer width="100%" height={height}>
            <BarChart
              width={width}
              height={height}
              data={data}
              margin={{ left: 10, right: 10 }}
            >
              <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.1} />
              <XAxis dataKey="time" />
              <YAxis dataKey="value" mirror />
              <Bar dataKey="value" fill="#82ca9d" isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        );
      case "area":
        return (
          <ResponsiveContainer width="100%" height={height}>
            <AreaChart
              width={width}
              height={height}
              data={data}
              margin={{ left: 10, right: 10, bottom: 30 }}
            >
              <CartesianGrid strokeDasharray="1 1" strokeOpacity={0.9} />
              <XAxis
                dataKey="date"
                tick={{ angle: -60, dy: 20, fontSize: 12 }}
              />
              <YAxis />
              <Tooltip
                isAnimationActive={false}
                // content={({ active, payload }) => {
                //   if (active && payload && payload.length) {
                //     // Wyświetla tylko dane dla aktywnego wykresu
                //     const currentPayload = payload.find(p => p.dataKey === activeKey);
                //     if (currentPayload) {
                //       return (
                //         <div className="custom-tooltip">
                //           <p>{currentPayload.dataKey}: {currentPayload.value}</p>
                //           <p>{`Date: ${currentPayload.payload.date}`}</p>
                //         </div>
                //       );
                //     }
                //   }
                //   return null; // Brak tooltipu, gdy nie ma aktywnego wykresu
                // }}
              />
              <Legend verticalAlign="top" />
              {Array.isArray(dataKey) ? (
                dataKey.map((key, index) => (
                  <Area
                    key={key}
                    dataKey={key}
                    stackId="1"
                    fill={colors[index % colors.length]} // Użyj koloru z listy
                    stroke={colors[index % colors.length]}
                    // onMouseEnter={() => handleMouseEnter(key)}  // Ustawia aktywne wykresy
                    // onMouseLeave={handleMouseLeave}  // Resetuje po opuszczeniu wykresu
                  />
                ))
              ) : (
                <Area
                  dataKey={dataKey}
                  stackId="1"
                  fill="#82ca9d"
                  stroke="#82ca9d"
                  isAnimationActive={false}
                />
              )}
            </AreaChart>
          </ResponsiveContainer>
        );
      default:
        return null;
    }
  }
}

GraphBlock.propTypes = {
  type: PropTypes.string.isRequired,
  data: PropTypes.array.isRequired,
};
