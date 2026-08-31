interface Props {
  lapA: Record<string, number>[]
  lapB: Record<string, number>[]
  lapATimeMs: number
  lapBTimeMs: number
}

const THRESHOLD = 10
const finite = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value)
const stateFor = (point: Record<string, number>) => finite(point.brake) && point.brake >= THRESHOLD ? 'brake' : finite(point.throttle) && point.throttle >= THRESHOLD ? 'throttle' : 'coast'
const color = (state: string, lap: 'A' | 'B') => ({
  throttle: lap === 'A' ? '#15803d' : '#86efac',
  brake: lap === 'A' ? '#dc2626' : '#fca5a5',
  coast: lap === 'A' ? '#4338ca' : '#c4b5fd',
}[state])

const coordinateKey = (lapA: Record<string, number>[], lapB: Record<string, number>[]) => ['y', 'z'].find((key) => [...lapA, ...lapB].every((point) => finite(point.x) && finite(point[key])))

const hoverText = (point: Record<string, number>, index: number, count: number, lapTime: number) =>
  `distance ${finite(point.dist) ? point.dist.toFixed(1) : 'unavailable'} m | speed ${point.speed ?? '—'} km/h | throttle ${point.throttle ?? '—'}% | brake ${point.brake ?? '—'}% | gear ${point.gear ?? '—'} | elapsed ${Math.round(lapTime * index / Math.max(count - 1, 1))} ms`

export default function RaceLineMap({ lapA, lapB, lapATimeMs, lapBTimeMs }: Props) {
  const axis = coordinateKey(lapA, lapB)
  if (!axis) return <p>Racing-line overlay is unavailable: both laps need consistent x/y or x/z coordinates.</p>
  const all = [...lapA, ...lapB]
  const xs = all.map((point) => point.x).filter(finite)
  const ys = all.map((point) => point[axis]).filter(finite)
  const minX = Math.min(...xs); const maxX = Math.max(...xs); const minY = Math.min(...ys); const maxY = Math.max(...ys)
  const scale = (value: number, min: number, max: number) => 20 + 760 * (value - min) / Math.max(max - min, 1)
  const point = (row: Record<string, number>) => ({ x: scale(row.x, minX, maxX), y: 800 - scale(row[axis], minY, maxY) })
  const renderSegments = (rows: Record<string, number>[], lap: 'A' | 'B', lapTime: number) => rows.slice(1).map((row, index) => {
    const previous = rows[index]
    if (!finite(previous.x) || !finite(previous[axis]) || !finite(row.x) || !finite(row[axis])) return null
    const a = point(previous); const b = point(row)
    return <line key={`${lap}-${index}`} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={color(stateFor(previous), lap)} strokeWidth={lap === 'A' ? 3 : 2} opacity={lap === 'A' ? 0.95 : 0.5}>
      <title>{hoverText(previous, index, rows.length, lapTime)}</title>
    </line>
  })
  const events = (rows: Record<string, number>[]) => {
    const detected: { index: number; type: string }[] = []
    for (let index = 1; index < rows.length; index += 1) {
      if (stateFor(rows[index]) !== 'brake' || stateFor(rows[index - 1]) === 'brake') continue
      const throttleIndex = rows.findIndex((row, candidate) => candidate > index && stateFor(row) === 'throttle')
      if (throttleIndex === -1) continue
      let apexIndex = index
      for (let candidate = index; candidate <= throttleIndex; candidate += 1) {
        if (finite(rows[candidate].speed) && (!finite(rows[apexIndex].speed) || rows[candidate].speed < rows[apexIndex].speed)) apexIndex = candidate
      }
      detected.push({ index, type: 'B' }, { index: apexIndex, type: 'A' }, { index: throttleIndex, type: 'T' })
      index = throttleIndex
    }
    return detected.slice(0, 12)
  }
  const labels = (rows: Record<string, number>[], lap: 'A' | 'B') => events(rows).map((event) => {
    const marker = point(rows[event.index])
    return <g key={`${lap}-${event.index}`}><circle cx={marker.x} cy={marker.y} r="4" fill={lap === 'A' ? '#111827' : '#6b7280'} /><text x={marker.x + 6} y={marker.y - 6} fontSize="11" fill={lap === 'A' ? '#111827' : '#6b7280'}>{lap}{event.type} {Math.round(rows[event.index].speed || 0)}</text></g>
  })
  return <div style={{ overflowX: 'auto' }}><svg viewBox="0 0 800 800" role="img" aria-label="Input-state racing lines" style={{ width: '100%', minWidth: 500, background: '#f8fafc', borderRadius: 8 }}>
    {renderSegments(lapB, 'B', lapBTimeMs)}{renderSegments(lapA, 'A', lapATimeMs)}{labels(lapB, 'B')}{labels(lapA, 'A')}
  </svg></div>
}
