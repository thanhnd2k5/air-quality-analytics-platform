import ReactECharts from 'echarts-for-react'
import type { TrendPoint } from '../api/overview'

type Props = {
  points: TrendPoint[]
  height?: number
}

export function TrendChart({ points, height = 360 }: Props) {
  const option = {
    color: ['#0d9488', '#64748b', '#d97706'],
    tooltip: { trigger: 'axis' },
    legend: { top: 0, data: ['PM2.5', 'PM10', 'O3'] },
    grid: { left: 48, right: 24, top: 40, bottom: 40 },
    xAxis: {
      type: 'category',
      data: points.map((p) => p.date_day),
      axisLabel: { hideOverlap: true },
    },
    yAxis: {
      type: 'value',
      name: 'µg/m³',
      splitLine: { lineStyle: { type: 'dashed', opacity: 0.4 } },
    },
    series: [
      {
        name: 'PM2.5',
        type: 'line',
        showSymbol: false,
        data: points.map((p) => p.pm25_ug_m3_avg),
        markLine: {
          symbol: 'none',
          label: {
            formatter: 'Ngưỡng PM2.5',
            position: 'insideStartTop',
            color: '#dc2626',
          },
          lineStyle: { color: '#dc2626', type: 'dashed' },
          data: [{ yAxis: 115 }],
        },
      },
      {
        name: 'PM10',
        type: 'line',
        showSymbol: false,
        data: points.map((p) => p.pm10_ug_m3_avg),
      },
      {
        name: 'O3',
        type: 'line',
        showSymbol: false,
        data: points.map((p) => p.o3_ug_m3_avg),
      },
    ],
  }

  return <ReactECharts option={option} style={{ height }} notMerge />
}
