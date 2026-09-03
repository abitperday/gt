import { memo, useEffect, useMemo, useRef, useState } from 'react'
import './LiveDDU.css'

type ConnectionState = 'connecting' | 'waiting' | 'live' | 'stale'

interface LiveFrame {
  packet_id?: number
  captured_at?: number
  car_id?: number
  speed_kmh?: number
  gear?: number
  suggested_gear?: number
  rpm?: number
  rpm_warning?: number | null
  rpm_limiter?: number | null
  throttle_pct?: number
  brake_pct?: number
  lap?: number
  total_laps?: number
  position?: number
  total_racers?: number
  best_lap_ms?: number | null
  last_lap_ms?: number | null
  delta_to_reference_ms?: number | null
  last_lap_delta_ms?: number | null
  lap_distance_m?: number
  session_id?: number
  position_x?: number | null
  position_y?: number | null
  elevation_m?: number | null
  track_trace?: Array<[number, number]> | null
  track_recording_lap?: number | null
  track_ready?: boolean
  track_tone?: 'neutral' | 'fast' | 'slow'
  fuel_l?: number | null
  fuel_capacity_l?: number | null
  boost?: number | null
  oil_pressure?: number | null
  oil_temp_c?: number | null
  water_temp_c?: number | null
  tyre_temp_fl_c?: number | null
  tyre_temp_fr_c?: number | null
  tyre_temp_rl_c?: number | null
  tyre_temp_rr_c?: number | null
  tyre_slip_fl?: number | null
  tyre_slip_fr?: number | null
  tyre_slip_rl?: number | null
  tyre_slip_rr?: number | null
  tcs?: number | null
  brake_bias?: number | null
  in_race?: boolean
  paused?: boolean
  lights_active?: boolean
  high_beams?: boolean
  low_beams?: boolean
}

const finite = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value)
const clamp = (value: unknown) => finite(value) ? Math.max(0, Math.min(100, value)) : 0
const numberOrDash = (value: unknown, digits = 0) => finite(value) ? value.toFixed(digits) : '—'

function formatLapTime(value: unknown) {
  if (!finite(value) || value <= 0) return '—'
  const milliseconds = Math.round(value)
  const minutes = Math.floor(milliseconds / 60_000).toString().padStart(2, '0')
  const seconds = Math.floor(milliseconds / 1_000 % 60).toString().padStart(2, '0')
  const millis = (milliseconds % 1_000).toString().padStart(3, '0')
  return `${minutes}:${seconds}.${millis}`
}

function SystemIcon({ type }: { type: 'water' | 'oil' }) {
  if (type === 'water') return <svg className="system-icon" viewBox="0 0 24 24" aria-hidden="true">
    <path d="M12 2.7C8.5 7.1 6.2 10 6.2 13.8A5.8 5.8 0 0 0 12 19.6a5.8 5.8 0 0 0 5.8-5.8C17.8 10 15.5 7.1 12 2.7Z" />
    <path d="M9.1 14.6c.4 1.3 1.5 2.2 2.9 2.4" />
  </svg>
  return <svg className="system-icon" viewBox="0 0 24 24" aria-hidden="true">
    <path d="M4.2 9.1h10.1l2.4 2.5h2.7v4.1h-3.1l-1.8 2.1H7.1l-1.3-2.1H3.2v-4.8h1Z" />
    <path d="M8.3 9.1V6.6h3.4v2.5M9.2 13.5h4.5" />
  </svg>
}

function AbsIcon() {
  return <svg className="assist-svg abs-svg" viewBox="0 0 64 44" aria-hidden="true"><circle cx="32" cy="22" r="19" fill="none" stroke="currentColor" strokeWidth="3" /><text x="32" y="27" textAnchor="middle" fill="currentColor" fontSize="14" fontWeight="800" fontFamily="Arial, sans-serif">ABS</text></svg>
}

function TcsIcon() {
  return <svg className="assist-svg tcs-svg" viewBox="0 0 64 52" aria-hidden="true"><path d="M17 28h30l-3-10c-.8-2.8-3.4-4.7-6.3-4.7H26.3c-2.9 0-5.5 1.9-6.3 4.7L17 28Z" fill="none" stroke="currentColor" strokeWidth="3" strokeLinejoin="round" /><path d="M14 28h36v10H14zM21 38v4M43 38v4M21 22h22M13 18l-7-4M51 18l7-4M12 45c7-1 10-4 10-8M52 45c-7-1-10-4-10-8" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" /></svg>
}

function HeadlightIcon() {
  return <svg className="headlight-svg" viewBox="0 0 64 44" aria-hidden="true"><path d="M11 10v24h9c7-2 11-6 11-12s-4-10-11-12h-9Z" fill="none" stroke="currentColor" strokeWidth="3" strokeLinejoin="round" /><path d="M36 11h18M36 17h22M36 23h24M36 29h22M36 35h18" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" /></svg>
}

function Tyre({ label, temperature, slip }: { label: string, temperature: unknown, slip: unknown }) {
  const slipClass = finite(slip) && slip > 0.18 ? 'spinning' : finite(slip) && slip < -0.18 ? 'locking' : ''
  const temperatureClass = !finite(temperature) ? 'unknown' : temperature < 65 ? 'cold' : temperature <= 100 ? 'operating' : 'hot'
  return <div className={`tyre ${label.toLowerCase()} ${temperatureClass} ${slipClass}`}>
    <span>{label}</span>
    <strong>{numberOrDash(temperature, 0)}°</strong>
    <small>{finite(slip) ? `${slip >= 0 ? '+' : ''}${(slip * 100).toFixed(0)}% slip` : 'slip —'}</small>
  </div>
}

function PedalBar({ label, value, tone }: { label: string, value: unknown, tone: 'brake' | 'throttle' }) {
  return <div className={`pedal ${tone}`}>
    <div className="pedal-heading"><span>{label}</span><strong>{numberOrDash(value)}<small>%</small></strong></div>
    <div className="pedal-track" aria-label={`${label}: ${numberOrDash(value)} percent`}>
      <i style={{ transform: `scaleY(${clamp(value) / 100})` }} />
    </div>
  </div>
}

type TrackPoint = { x: number, y: number }
type TrackTone = 'neutral' | 'fast' | 'slow'
type TrackGeometry = { path: string, project: (point: TrackPoint) => TrackPoint }

const TrackTrace = memo(function TrackTrace({ geometry, tone }: { geometry: TrackGeometry | null, tone: TrackTone }) {
  return geometry?.path ? <polyline points={geometry.path} className={`track-line ${tone}`} /> : null
})

function TrackMap({ frame }: { frame: LiveFrame | null }) {
  const [trace, setTrace] = useState<TrackPoint[]>([])
  const traceSession = useRef<number | null>(null)

  useEffect(() => {
    const active = !!frame && frame.in_race !== false && finite(frame.lap) && frame.lap > 0
    const session = finite(frame?.session_id) ? frame.session_id : null
    if (!active) {
      traceSession.current = null
      setTrace([])
      return
    }
    if (traceSession.current !== session) {
      traceSession.current = session
      setTrace([])
    }
    if (Array.isArray(frame.track_trace)) {
      setTrace(frame.track_trace.flatMap(([x, y]) => finite(x) && finite(y) ? [{ x, y }] : []))
    }
  }, [frame?.in_race, frame?.lap, frame?.session_id, frame?.track_trace])

  const marker = finite(frame?.position_x) && finite(frame?.position_y)
    ? { x: frame.position_x, y: frame.position_y }
    : null
  const ready = !!frame?.track_ready
  // This runs only for a server trail snapshot, not for each 25 Hz marker update.
  // GT7's horizontal plane is X/Y; Z is elevation.
  const geometry = useMemo<TrackGeometry | null>(() => {
    if (!trace.length) return null
    const minX = Math.min(...trace.map((point) => point.x))
    const maxX = Math.max(...trace.map((point) => point.x))
    const minY = Math.min(...trace.map((point) => point.y))
    const maxY = Math.max(...trace.map((point) => point.y))
    const span = Math.max(maxX - minX, maxY - minY, 1)
    const project = (point: TrackPoint) => ({
      x: 50 + ((point.x - (minX + maxX) / 2) / span) * 82,
      y: 50 - ((point.y - (minY + maxY) / 2) / span) * 82,
    })
    return {
      path: trace.map(project).map((point) => `${point.x.toFixed(2)},${point.y.toFixed(2)}`).join(' '),
      project,
    }
  }, [trace])
  const projectedMarker = marker && geometry ? geometry.project(marker) : null
  const tone: TrackTone = frame?.track_tone === 'fast' || frame?.track_tone === 'slow' ? frame.track_tone : 'neutral'
  const active = !!frame && frame.in_race !== false && finite(frame.lap) && frame.lap > 0
  const status = !active
    ? 'WAITING FOR TELEMETRY'
    : !marker
      ? 'POSITION DATA UNAVAILABLE'
      : ready
        ? 'TRACE READY'
        : finite(frame?.track_recording_lap)
          ? `LEARNING LAP ${frame.track_recording_lap}`
          : 'WAITING FOR LAP START'
  const state = !marker ? 'unavailable' : ready ? 'ready' : 'recording'

  return <section className="live-track-map" aria-label="Live circuit map">
    <div className="track-map-heading"><span>TRACK MAP</span><b className={state}>{status}</b></div>
    <svg viewBox="0 0 100 100" role="img" aria-label={status} preserveAspectRatio="xMidYMid meet">
      <rect x="2" y="2" width="96" height="96" rx="4" className="track-map-frame" />
      <TrackTrace geometry={geometry} tone={tone} />
      {projectedMarker && <g className="track-marker" transform={`translate(${projectedMarker.x} ${projectedMarker.y})`}><circle r="4.6" /><circle r="2.25" /></g>}
    </svg>
    <small>{ready ? 'Full-lap trace retained by the telemetry hub' : 'Waiting for a complete live lap'}</small>
  </section>
}

export default function LiveDDU() {
  const [connection, setConnection] = useState<ConnectionState>('connecting')
  const [message, setMessage] = useState('Connecting to the local telemetry API…')
  const [frame, setFrame] = useState<LiveFrame | null>(null)
  const [lapStartedAt, setLapStartedAt] = useState<number | null>(null)
  const [trackedLap, setTrackedLap] = useState<number | null>(null)
  const [pausedAt, setPausedAt] = useState<number | null>(null)
  const [pausedDurationMs, setPausedDurationMs] = useState(0)
  const [bestDisplay, setBestDisplay] = useState<'gain' | 'best' | null>(null)
  const [headlightBlink, setHeadlightBlink] = useState(false)
  const previousBeam = useRef<string>('off')
  const blinkTimer = useRef<number | null>(null)
  const pendingFrame = useRef<LiveFrame | null>(null)
  const animationFrame = useRef<number | null>(null)

  useEffect(() => {
    document.body.classList.add('live-ddu-body')
    let socket: WebSocket | null = null
    let reconnectTimer: number | null = null
    let stopped = false
    const connect = () => {
      setConnection('connecting')
      setMessage('Connecting to the local telemetry API…')
      const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
      const apiHost = `${window.location.hostname}:8000`
      socket = new WebSocket(`${protocol}://${apiHost}/ws/live`)
      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data) as { type?: string, status?: string, message?: string, frame?: LiveFrame }
          if (payload.type === 'frame' && payload.frame && typeof payload.frame === 'object') {
            pendingFrame.current = payload.frame
            setConnection('live')
            setMessage('Receiving GT7 telemetry')
            if (animationFrame.current === null) animationFrame.current = window.requestAnimationFrame(() => {
              if (pendingFrame.current) setFrame(pendingFrame.current)
              animationFrame.current = null
            })
          } else if (payload.type === 'status') {
            const next = payload.status === 'stale' ? 'stale' : 'waiting'
            setConnection(next)
            setMessage(payload.message || (next === 'stale' ? 'GT7 signal is stale' : 'Waiting for GT7'))
          }
        } catch { /* Ignore malformed frames; the next valid latest frame replaces them. */ }
      }
      socket.onerror = () => socket?.close()
      socket.onclose = () => {
        if (stopped) return
        setConnection('connecting')
        setMessage('API disconnected. Retrying…')
        reconnectTimer = window.setTimeout(connect, 1500)
      }
    }
    connect()
    return () => {
      document.body.classList.remove('live-ddu-body')
      stopped = true
      socket?.close()
      if (reconnectTimer !== null) window.clearTimeout(reconnectTimer)
      if (animationFrame.current !== null) window.cancelAnimationFrame(animationFrame.current)
    }
  }, [])

  useEffect(() => {
    if (!finite(frame?.lap) || !finite(frame?.captured_at)) return
    if (frame.lap <= 0 || frame.in_race === false) {
      setTrackedLap(null)
      setLapStartedAt(null)
      setPausedAt(null)
      setPausedDurationMs(0)
      return
    }
    if (trackedLap !== frame.lap) {
      setTrackedLap(frame.lap)
      setLapStartedAt(frame.captured_at)
      setPausedAt(null)
      setPausedDurationMs(0)
    }
  }, [frame?.lap, frame?.captured_at, trackedLap])

  useEffect(() => {
    const capturedAt = frame?.captured_at
    if (!frame || !finite(capturedAt)) return
    if (frame.paused) {
      if (pausedAt === null) setPausedAt(capturedAt)
    } else if (pausedAt !== null) {
      setPausedDurationMs((total) => total + Math.max(0, (capturedAt - pausedAt) * 1000))
      setPausedAt(null)
    }
  }, [frame?.paused, frame?.captured_at, pausedAt])

  useEffect(() => {
    if (!finite(frame?.lap) || !finite(frame?.last_lap_delta_ms) || frame.last_lap_delta_ms >= 0) return
    setBestDisplay('gain')
    const timer = window.setTimeout(() => setBestDisplay('best'), 5000)
    return () => window.clearTimeout(timer)
  }, [frame?.lap, frame?.last_lap_delta_ms])

  useEffect(() => {
    const beam = frame?.high_beams ? 'high' : frame?.low_beams ? 'low' : 'off'
    if (beam === 'high' && previousBeam.current !== 'high') {
      setHeadlightBlink(true)
      if (blinkTimer.current !== null) window.clearTimeout(blinkTimer.current)
      blinkTimer.current = window.setTimeout(() => setHeadlightBlink(false), 500)
    }
    previousBeam.current = beam
  }, [frame?.high_beams, frame?.low_beams])

  const currentLapMs = finite(frame?.captured_at) && finite(frame?.lap) && frame.lap > 0 && frame?.in_race !== false && lapStartedAt !== null
    ? Math.max(0, (frame.captured_at - lapStartedAt) * 1000 - pausedDurationMs - (pausedAt !== null ? Math.max(0, (frame.captured_at - pausedAt) * 1000) : 0))
    : null
  const lastLapDeltaMs = finite(frame?.last_lap_delta_ms) ? frame.last_lap_delta_ms : null
  const showLapDelta = finite(frame?.lap) && frame.lap > 2 && frame?.in_race !== false && lastLapDeltaMs !== null
  const rpmMaximum = Math.max(finite(frame?.rpm_limiter) && frame.rpm_limiter > 0 ? frame.rpm_limiter : 0, finite(frame?.rpm_warning) && frame.rpm_warning > 0 ? frame.rpm_warning * 1.08 : 0, finite(frame?.rpm) ? frame.rpm : 0, 1)
  const rpmPercent = Math.min(100, Math.max(0, ((frame?.rpm || 0) / rpmMaximum) * 100))
  const atShift = finite(frame?.rpm_warning) && frame.rpm_warning > 0 && (frame?.rpm || 0) >= frame.rpm_warning
  const fuelPercent = finite(frame?.fuel_l) && finite(frame?.fuel_capacity_l) && frame.fuel_capacity_l > 0 ? Math.max(0, Math.min(100, frame.fuel_l / frame.fuel_capacity_l * 100)) : null
  const fuelState = fuelPercent === null ? 'unknown' : fuelPercent <= 10 ? 'critical' : fuelPercent <= 30 ? 'reserve' : 'normal'
  const fuelLabel = fuelState === 'critical' ? 'LOW FUEL' : fuelState === 'reserve' ? 'RESERVE' : 'FUEL'
  const slips = useMemo(() => [frame?.tyre_slip_fl, frame?.tyre_slip_fr, frame?.tyre_slip_rl, frame?.tyre_slip_rr].filter(finite), [frame])
  const lockup = (frame?.speed_kmh || 0) >= 20 && (frame?.brake_pct || 0) >= 15 && slips.some((slip) => slip <= -0.18)
  const wheelspin = (frame?.speed_kmh || 0) >= 10 && (frame?.throttle_pct || 0) >= 20 && slips.some((slip) => slip >= 0.18)
  const tractionState = slips.length === 0 ? 'unknown' : wheelspin ? 'active' : 'off'
  const brakingState = slips.length === 0 ? 'unknown' : lockup ? 'active' : 'off'
  const lightState = frame?.lights_active || frame?.high_beams || frame?.low_beams ? 'on' : 'off'
  const gear = finite(frame?.gear) && frame.gear > 0 ? frame.gear : 'N'
  const panelInactive = !frame || !finite(frame.lap) || frame.lap <= 0 || frame.in_race === false
  const raceFinished = !!frame && finite(frame.lap) && finite(frame.total_laps) && frame.total_laps > 0 && frame.lap > frame.total_laps

  return <main className="ddu-shell">
    {(panelInactive || raceFinished) && <div className="ddu-inactive-overlay" role="status" aria-live="polite"><div>{raceFinished ? <><span className="inactive-icon">✓</span><strong>CORRIDA FINALIZADA!</strong><small>SIGA PARA A TELA DE ANÁLISE PARA VER TODOS OS DETALHES</small></> : <><span className="inactive-icon">◌</span><strong>INICIE UMA CORRIDA</strong><small>PARA ATIVAR O PAINEL</small></>}</div></div>}
    <header className="ddu-header">
      <div className="identity"><strong className="live-title">GT7 / LIVE DDU</strong><span className={`connection ${connection}`}><i />{connection}</span></div>
      <span className="connection-message">{message}</span>
      <nav><a href="/">Recorded analysis</a><button onClick={() => document.documentElement.requestFullscreen?.()}>Full screen</button></nav>
    </header>
    <section className={`speed-rpm-band ${atShift ? 'shift' : ''}`} aria-label={`Speed ${numberOrDash(frame?.speed_kmh)} kilometres per hour`}>
      <div className={`band-scale ${rpmPercent >= 88 ? 'red' : rpmPercent >= 70 ? 'amber' : 'green'}`}><i style={{ transform: `scaleX(${rpmPercent / 100})` }} /></div>
      <div className="band-rpm">{numberOrDash(frame?.rpm)} RPM</div>
    </section>
    <section className="ddu-grid">
      <aside className="race-card panel">
        {/* <div className="panel-heading"><span>RACE CONTEXT</span><b>{frame?.in_race ? 'ON TRACK' : 'SESSION'}</b></div>/ */}
        <div className="race-values">
          <div className="race-stat position"><span>POSITION</span><strong>{finite(frame?.position) && frame.position > 0 ? frame.position : '—'}<small> / {finite(frame?.total_racers) && frame.total_racers > 0 ? frame.total_racers : '—'}</small></strong></div>
          <div className="race-stat laps"><span>LAPS</span><strong>{finite(frame?.lap) && frame.lap > 0 ? frame.lap : '—'}<small> / {finite(frame?.total_laps) && frame.total_laps > 0 ? frame.total_laps : '—'}</small></strong><em>{numberOrDash(frame?.lap_distance_m, 0)} m</em></div>
          <TrackMap frame={frame} />
          <div className="current-time lap-time"><strong>{formatLapTime(currentLapMs)}</strong></div>
          <div className="best-time lap-time"><strong>{formatLapTime(frame?.best_lap_ms)}</strong></div>
          <div className="last-time lap-time"><strong>{formatLapTime(frame?.last_lap_ms)}</strong></div>
        </div>
      </aside>
      <section className="primary-readout panel">
        <div className="control-composition">
          <PedalBar label="BRAKE" value={frame?.brake_pct} tone="brake" />
          <div className={`gear-rpm ${atShift ? 'shift' : ''}`} aria-label={`RPM ${numberOrDash(frame?.rpm)}`}>
            <div className="gear-indicators"><div className={`lighting-indicator ${lightState} ${headlightBlink ? 'blink' : ''}`} role="status" aria-label={`Lights: ${lightState}`}><span className="light-icon" aria-hidden="true"><HeadlightIcon /></span></div><div className={`mini-indicator abs ${brakingState}`} aria-label={`ABS: ${brakingState}`}><AbsIcon /></div><div className={`mini-indicator tcs ${tractionState}`} aria-label={`TCS: ${tractionState}`}><TcsIcon /></div></div><div className={`gear`}><strong style={{fontSize: '230px', fontWeight:'300', color: "yellow"}}>{gear}</strong></div>
            <div><strong style={{fontSize: '40px'}}>{numberOrDash(frame?.speed_kmh).split('').map((digit, index) => <i key={`${digit}-${index}`}>{digit}</i>)}</strong><span>KM/H</span></div>
            <div className="gear-support"><div className="suggestion"><strong style={{fontWeight: 200, fontSize: '65px', color: 'red'}}>{finite(frame?.suggested_gear) && frame.suggested_gear > 0 && frame.suggested_gear < 15 ? frame.suggested_gear : '—'}</strong></div>{showLapDelta && <div className={`delta ${lastLapDeltaMs > 0 ? 'behind' : 'ahead'}`}><span>DELTA</span><strong>{lastLapDeltaMs < 0 && bestDisplay === 'best' ? 'BEST' : `${lastLapDeltaMs > 0 ? '+' : '−'}${(Math.abs(lastLapDeltaMs) / 1000).toFixed(3)}`}<small>{lastLapDeltaMs < 0 && bestDisplay === 'best' ? '' : 's'}</small></strong></div>}</div>
          </div>
          <PedalBar label="THROTTLE" value={frame?.throttle_pct} tone="throttle" />
        </div>
        <div className="warnings" aria-live="polite">{atShift && <strong className="shift-warning">SHIFT NOW</strong>}{lockup && <strong className="lockup">LOCKUP</strong>}{wheelspin && <strong className="wheelspin">WHEELSPIN</strong>}{frame?.paused && <strong>PAUSED</strong>}</div>
      </section>
      <aside className="systems-card panel">
        <div className="panel-heading"><span>VEHICLE STATE</span><b>{frame?.paused ? 'PAUSED' : 'LIVE'}</b></div>
        <div className={`fuel ${fuelState}`}><div className="fuel-title"><span>{fuelLabel}</span><strong>{numberOrDash(frame?.fuel_l, 1)} <small>L</small></strong></div><div className="fuel-track"><i style={{ width: `${fuelPercent || 0}%` }} /></div><small>{fuelPercent === null ? 'capacity unavailable' : `${fuelPercent.toFixed(0)}% · ${numberOrDash(frame?.fuel_capacity_l, 1)} L capacity`}</small></div>
        <section className="systems-tyres" style={{marginBottom: '10px'}}><div className="panel-heading"></div><div className="tyre-car" aria-label="Tyre temperature layout"><Tyre label="FL" temperature={frame?.tyre_temp_fl_c} slip={frame?.tyre_slip_fl} /><div className="car-outline" aria-hidden="true"><i /></div><Tyre label="FR" temperature={frame?.tyre_temp_fr_c} slip={frame?.tyre_slip_fr} /><Tyre label="RL" temperature={frame?.tyre_temp_rl_c} slip={frame?.tyre_slip_rl} /><Tyre label="RR" temperature={frame?.tyre_temp_rr_c} slip={frame?.tyre_slip_rr} /></div></section>
        <div className="system-readings">
          <div className="system-reading water"><SystemIcon type="water" /><span>WATER</span><strong>{numberOrDash(frame?.water_temp_c, 0)}<small>°C</small></strong></div>
          <div className="system-reading oil"><SystemIcon type="oil" /><span>OIL</span><strong>{numberOrDash(frame?.oil_temp_c, 0)}<small>°C</small></strong><em>{numberOrDash(frame?.oil_pressure, 1)} pressure</em></div>
        </div>
      </aside>
    </section>
    {/* <footer>Raw live GT7 measurements · No live delta or coaching · Slip alerts require measured slip plus driver input</footer> */}
  </main>
}
