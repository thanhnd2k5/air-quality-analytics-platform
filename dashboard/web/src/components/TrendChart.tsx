import { useMemo } from 'react'
import type { TrendPoint } from '../api/overview'
import { INK, NEUTRAL_SERIES, SERIES } from '../theme'
import { Chart } from './Chart'

type Props = {
  points: TrendPoint[]
  height?: number
}

/** Daily PM2.5 (the subject of the project) up front; PM10 as a quiet reference line. */
export function TrendChart({ points, height = 360 }: Props) {
  const option = useMemo(
    () => ({
      tooltip: {
        trigger: 'axis',
        valueFormatter: (v: number | null) => (v == null ? '—' : `${v.toFixed(1)} µg/m³`),
      },
      legend: { data: ['PM2.5', 'PM10'] },
      grid: { left: 8, right: 16, top: 48, bottom: 8, containLabel: true },
      xAxis: {
        type: 'category',
        data: points.map((p) => p.date_day),
        axisLabel: { formatter: (d: string) => `${d.slice(8, 10)}/${d.slice(5, 7)}` },
      },
      yAxis: { type: 'value', name: 'µg/m³' },
      series: [
        {
          name: 'PM10',
          type: 'line',
          showSymbol: false,
          color: NEUTRAL_SERIES.soft,
          lineStyle: { width: 1.5 },
          data: points.map((p) => p.pm10_ug_m3_avg),
        },
        {
          name: 'PM2.5',
          type: 'line',
          showSymbol: false,
          color: SERIES.blue,
          areaStyle: { opacity: 0.08 },
          z: 3,
          data: points.map((p) => p.pm25_ug_m3_avg),
          markLine: {
            symbol: 'none',
            silent: true,
            label: { formatter: '115 µg/m³', position: 'insideEndTop', color: INK.secondary, fontSize: 11 },
            lineStyle: { color: INK.secondary, type: 'dashed', width: 1 },
            data: [{ yAxis: 115 }],
          },
        },
      ],
    }),
    [points],
  )

  return (
    <Chart
      option={option}
      height={height}
      label="Biểu đồ đường PM2.5 và PM10 trung bình theo ngày, có vạch ngưỡng 115 µg/m³."
    />
  )
}
