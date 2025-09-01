// src/components/RiskChart.js
import {Doughnut} from 'react-chartjs-2';
import {Chart as ChartJS, ArcElement, Tooltip, Legend} from 'chart.js';
ChartJS.register(ArcElement, Tooltip, Legend);

export const RiskChart = ({chartData}) => {
  const data = {
    labels: chartData.labels,
    datasets: [
      {
        data: chartData.data,
        backgroundColor: ['#10B981', '#F59E0B', '#EF4444'],
        borderColor: ['#ffffff'],
        borderWidth: 2,
      },
    ],
  };
  const options = {
    responsive: true,
    plugins: {
      legend: {position: 'bottom'},
      title: {display: true, text: 'Calls by Risk Level'},
    },
  };
  return <Doughnut data={data} options={options} />;
};
