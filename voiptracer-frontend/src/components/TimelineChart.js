// src/components/TimelineChart.js
import {Line} from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
);

export const TimelineChart = ({chartData}) => {
  const data = {
    labels: chartData.labels.map(l => new Date(l).toLocaleTimeString()),
    datasets: [
      {
        label: 'Calls per Hour',
        data: chartData.data,
        borderColor: 'rgb(79, 70, 229)',
        backgroundColor: 'rgba(79, 70, 229, 0.5)',
        fill: true,
      },
    ],
  };
  const options = {
    responsive: true,
    plugins: {
      legend: {display: false},
      title: {display: true, text: 'Call Volume Over Time'},
    },
  };
  return <Line options={options} data={data} />;
};
