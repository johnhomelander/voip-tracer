// src/components/TimelineChart.js
import { Line } from "react-chartjs-2";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  TimeScale,
} from "chart.js";
import "chartjs-adapter-date-fns";
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  TimeScale
);

export const TimelineChart = ({ chartData }) => {
  if (!chartData || !chartData.labels || !chartData.data) {
    return <p>Loading chart data...</p>;
  }

  const formattedData = chartData.labels.map((label, index) => ({
    x: new Date(label), // Use a JavaScript Date object for the x-axis
    y: chartData.data[index], // Use the count for the y-axis
  }));

  const data = {
    datasets: [
      {
        label: "Calls per Hour",
        data: formattedData,
        borderColor: "rgb(79, 70, 229)",
        backgroundColor: "rgba(79, 70, 229, 0.5)",
        fill: true,
      },
    ],
  };
  const options = {
    responsive: true,
    plugins: {
      legend: { display: false },
      title: { display: true, text: "Call Volume Over Time" },
    },
    scales: {
      x: {
        type: "time",
        time: {
          unit: "hour",
          tooltipFormat: "MMM d, yyyy HH:mm",
          displayFormats: {
            hour: "HH:mm",
          },
        },
        title: {
          display: true,
          text: "Time (UTC)",
        },
      },
      y: {
        beginAtZero: true,
        title: {
          display: true,
          text: "Number of Calls",
        },
      },
    },
  };
  return <Line options={options} data={data} />;
};
