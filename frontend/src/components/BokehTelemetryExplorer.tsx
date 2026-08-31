import { useEffect, useMemo, useRef } from 'react'
import { figure } from '@bokeh/bokehjs/build/js/lib/api/figure'
import { gridplot } from '@bokeh/bokehjs/build/js/lib/api/gridplot'
import { show } from '@bokeh/bokehjs/build/js/lib/api/io'
import { ColumnDataSource } from '@bokeh/bokehjs/build/js/lib/models/sources/column_data_source'
import { Range1d } from '@bokeh/bokehjs/build/js/lib/models/ranges/range1d'
import { HoverTool } from '@bokeh/bokehjs/build/js/lib/models/tools/inspectors/hover_tool'
import { CrosshairTool } from '@bokeh/bokehjs/build/js/lib/models/tools/inspectors/crosshair_tool'
import type { LapComparison } from '../api/schema'

interface Props {
  lapA: Record<string, number>[]
  lapB: Record<string, number>[]
  lapATimeMs: number
  lapBTimeMs: number
  comparison?: LapComparison
}

const ORANGE = '#f97316'
const BLUE = '#2563eb'
const METRICS = [
  ['speed', 'Speed (km/h)'],
  ['throttle', 'Throttle (%)'],
  ['brake', 'Brake (%)'],
  ['gear', 'Gear'],
] as const

type Series = { distance: number[]; values: Record<string, number[]> }

const finite = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value)

const seriesFrom = (records: Record<string, number>[], lapTimeMs: number): Series | null => {
  const validDistances = records.map((row) => row.dist).filter(finite)
  if (validDistances.length < 3) return null
  const changes = validDistances.slice(1).map((distance, index) => distance - validDistances[index])
  const positives = changes.filter((change) => change > 0).sort((a, b) => a - b)
  const median = positives[Math.floor(positives.length / 2)] || 0
  const distance: number[] = []
  const values: Record<string, number[]> = { speed: [], throttle: [], brake: [], gear: [], elapsed_ms: [] }
  let previousDistance: number | null = null
  for (const [index, row] of records.entries()) {
    const currentDistance = row.dist
    const isGap = !finite(currentDistance) || previousDistance !== null && (currentDistance < previousDistance || median > 0 && currentDistance - previousDistance > median * 25)
    distance.push(finite(currentDistance) ? currentDistance : Number.NaN)
    for (const [metric] of METRICS) values[metric].push(!isGap && finite(row[metric]) ? row[metric] : Number.NaN)
    values.elapsed_ms.push(lapTimeMs * index / Math.max(records.length - 1, 1))
    if (finite(currentDistance)) previousDistance = currentDistance
  }
  return { distance, values }
}

export default function BokehTelemetryExplorer({ lapA, lapB, lapATimeMs, lapBTimeMs, comparison }: Props) {
  const mountRef = useRef<HTMLDivElement>(null)
  const seriesA = useMemo(() => seriesFrom(lapA, lapATimeMs), [lapA, lapATimeMs])
  const seriesB = useMemo(() => seriesFrom(lapB, lapBTimeMs), [lapB, lapBTimeMs])

  useEffect(() => {
    const mount = mountRef.current
    if (!mount || !seriesA || !seriesB) return
    mount.replaceChildren()
    const maxDistance = Math.max(...seriesA.distance.filter(finite), ...seriesB.distance.filter(finite))
    const sharedRange = new Range1d({ start: 0, end: maxDistance })
    const sourceA = new ColumnDataSource({ data: { distance: seriesA.distance, ...seriesA.values } })
    const sourceB = new ColumnDataSource({ data: { distance: seriesB.distance, ...seriesB.values } })
    const plots = METRICS.map(([metric, label], index) => {
      const plot = figure({
        width: 1000,
        height: 190,
        x_range: sharedRange,
        y_axis_label: label,
        x_axis_label: index === METRICS.length - 1 ? 'Physical lap distance (m)' : '',
        tools: 'pan,wheel_zoom,box_zoom,reset',
        active_scroll: 'wheel_zoom',
      })
      const a = plot.line({ x: { field: 'distance' }, y: { field: metric }, source: sourceA, line_color: ORANGE, line_width: 2, legend_label: 'Lap A' })
      const b = plot.line({ x: { field: 'distance' }, y: { field: metric }, source: sourceB, line_color: BLUE, line_width: 2, legend_label: 'Lap B' })
      plot.add_tools(new HoverTool({ renderers: [a, b], mode: 'vline', tooltips: [['Distance', '@distance{0.0} m'], [label, `@${metric}{0.0}`], ['Elapsed', '@elapsed_ms{0} ms']] }))
      plot.add_tools(new CrosshairTool({ dimensions: 'height' }))
      return plot
    })
    if (comparison?.available && comparison.points?.length) {
      const spanA = Math.max(...seriesA.distance.filter(finite))
      const deltaSource = new ColumnDataSource({ data: {
        distance: comparison.points.map((point) => point.progress * spanA),
        delta: comparison.points.map((point) => point.delta_ms),
        elapsed_a_ms: comparison.points.map((point) => point.elapsed_a_ms),
        elapsed_b_ms: comparison.points.map((point) => point.elapsed_b_ms),
      } })
      const delta = figure({ width: 1000, height: 190, x_range: sharedRange, y_axis_label: 'Delta A − B (ms)', x_axis_label: 'Physical lap distance (m)', tools: 'pan,wheel_zoom,box_zoom,reset', active_scroll: 'wheel_zoom' })
      const line = delta.line({ x: { field: 'distance' }, y: { field: 'delta' }, source: deltaSource, line_color: '#7c3aed', line_width: 2 })
      delta.add_tools(new HoverTool({ renderers: [line], mode: 'vline', tooltips: [['Distance', '@distance{0.0} m'], ['Delta A − B', '@delta{0.0} ms'], ['Lap A elapsed', '@elapsed_a_ms{0} ms'], ['Lap B elapsed', '@elapsed_b_ms{0} ms']] }))
      delta.add_tools(new CrosshairTool({ dimensions: 'height' }))
      plots.push(delta)
    }
    void show(gridplot(plots, { ncols: 1, merge_tools: true }), mount)
    return () => mount.replaceChildren()
  }, [seriesA, seriesB, comparison])

  if (!seriesA || !seriesB) return <p>Linked telemetry explorer is unavailable: both laps need at least three valid distance samples.</p>
  return <div ref={mountRef} style={{ overflowX: 'auto', minHeight: 760 }} />
}
