import { Box } from '@mantine/core'
import * as echarts from 'echarts'
import ReactECharts from 'echarts-for-react'
import { useMemo } from 'react'
import { fmtAxis } from '../format'
import { FONT_FAMILY, INK, SERIES_ORDER } from '../theme'

// One ECharts theme for every chart: recessive axes and grid, thin marks, card-like tooltip.
echarts.registerTheme('aq', {
  color: SERIES_ORDER,
  backgroundColor: 'transparent',
  textStyle: { fontFamily: FONT_FAMILY, color: INK.secondary, fontSize: 12 },
  // Top-right, opposite the y-axis name. (Its scroll type is set per option in <Chart>:
  // ECharts resolves a component's type before applying the theme.)
  legend: {
    left: 'right', // ECharts defaults left to 'center', which would win over `right`
    top: 0,
    icon: 'roundRect',
    itemWidth: 10,
    itemHeight: 10,
    itemGap: 16,
    textStyle: { color: INK.secondary, fontSize: 12 },
  },
  tooltip: {
    backgroundColor: INK.surface,
    borderColor: INK.border,
    borderWidth: 1,
    padding: [8, 12],
    textStyle: { color: INK.primary, fontSize: 12 },
    extraCssText: 'border-radius: 8px; box-shadow: 0 6px 20px rgba(15, 23, 42, 0.08);',
    axisPointer: { lineStyle: { color: INK.axis }, crossStyle: { color: INK.axis } },
  },
  categoryAxis: {
    axisLine: { show: true, lineStyle: { color: INK.axis } },
    axisTick: { show: false },
    axisLabel: { color: INK.muted, fontSize: 11, hideOverlap: true },
    splitLine: { show: false },
    nameTextStyle: { color: INK.muted, fontSize: 11 },
  },
  valueAxis: {
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: { color: INK.muted, fontSize: 11 },
    splitLine: { show: true, lineStyle: { color: INK.grid } },
    nameTextStyle: { color: INK.muted, fontSize: 11, align: 'left' },
  },
  line: { symbol: 'circle', symbolSize: 6, lineStyle: { width: 2 } },
  bar: { barMaxWidth: 32, itemStyle: { borderRadius: [4, 4, 0, 0] } },
  scatter: { symbolSize: 8 },
  visualMap: { textStyle: { color: INK.muted, fontSize: 11 } },
})

type Axis = { type?: string; axisLabel?: { formatter?: unknown } }

// Value axes get vi-VN tick labels ("0,25", "1.000") unless the page set a formatter.
function withViTicks(axes: unknown, defaultType: string) {
  if (!axes) return axes
  const fix = (a: Axis) =>
    (a.type ?? defaultType) === 'value' && !a.axisLabel?.formatter
      ? { ...a, axisLabel: { ...a.axisLabel, formatter: fmtAxis } }
      : a
  return Array.isArray(axes) ? axes.map(fix) : fix(axes as Axis)
}

const reducedMotion =
  typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

type Props = {
  option: Record<string, unknown>
  height: number
  /** Short description for screen readers (the chart canvas itself is not readable). */
  label: string
}

export function Chart({ option, height, label }: Props) {
  // Rebuilt only when the caller's option changes, so parent re-renders don't touch ECharts.
  const merged = useMemo(() => {
    // One-row legend that scrolls on narrow screens instead of wrapping over the plot.
    const legend = option.legend ? { type: 'scroll', ...(option.legend as object) } : undefined
    return {
      animationDuration: 400,
      ...option,
      ...(option.xAxis ? { xAxis: withViTicks(option.xAxis, 'category') } : {}),
      ...(option.yAxis ? { yAxis: withViTicks(option.yAxis, 'value') } : {}),
      ...(legend ? { legend } : {}),
      ...(reducedMotion ? { animation: false } : {}),
    }
  }, [option])
  const style = useMemo(() => ({ height, width: '100%' }), [height])
  return (
    <Box role="img" aria-label={label}>
      <ReactECharts
        theme="aq"
        option={merged}
        style={style}
        notMerge
        lazyUpdate
      />
    </Box>
  )
}
