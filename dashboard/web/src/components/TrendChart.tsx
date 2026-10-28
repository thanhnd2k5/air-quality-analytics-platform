import { useMemo } from 'react'
import type { TrendPoint } from '../api/overview'
import { fmtNum } from '../format'
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
        // Date as the pickers show it, PM2.5 first (series order puts PM10 underneath).
        formatter: (params: { dataIndex: number }[]) => {
          const p = points[params[0]?.dataIndex ?? 0]
          if (!p) return ''
          const d = p.date_day
          const row = (color: string, name: string, v: number | null) =>
            `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${color};margin-right:6px"></span>` +
            `${name}: <b>${v == null ? '—' : `${fmtNum(v)} µg/m³`}</b>`
          return [
            `<b>${d.slice(8, 10)}/${d.slice(5, 7)}/${d.slice(0, 4)}</b>`,
            row(SERIES.blue, 'PM2.5', p.pm25_ug_m3_avg),
            row(NEUTRAL_SERIES.soft, 'PM10', p.pm10_ug_m3_avg),
          ].join('<br/>')
        },
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
