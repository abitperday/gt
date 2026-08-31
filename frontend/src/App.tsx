import { useEffect, useState } from 'react'
import { Chart as ChartJS, LinearScale, PointElement, LineElement, Title, Legend } from 'chart.js'
import { TrajectoryGraph } from './graphs/chartjs'
import BokehTelemetryExplorer from './components/BokehTelemetryExplorer'
import RaceLineMap from './components/RaceLineMap'
import zoomPlugin from 'chartjs-plugin-zoom'
import { useLapComparison, useLapTelemetry, useSessionDetail, useSessionLaps, useSessions, useTrackLayout, useTrackLayouts } from './api/hooks'
import { createPlaybackTrajectory, positionAtElapsed } from './playback'

ChartJS.register(
  LinearScale,
  LineElement,
  PointElement,
  Title,
  // Tooltip,
  Legend,
  zoomPlugin
)

function App() {
  const [sessionId, setSessionId] = useState('')
  const [lapA, setLapA] = useState(0)
  const [lapB, setLapB] = useState(0)
  const [layoutId, setLayoutId] = useState('')
  const [playbackTimeMs, setPlaybackTimeMs] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)
  const [playbackSpeed, setPlaybackSpeed] = useState(1)
  const { data: sessions, isLoading: sessionsLoading, isError: sessionsError } = useSessions()
  const selectedSessionId = sessionId || sessions?.[0]?.id || ''
  const { data: laps, isLoading: lapsLoading, isError: lapsError } = useSessionLaps(selectedSessionId)
  const sessionDetail = useSessionDetail(selectedSessionId)
  const trackLayouts = useTrackLayouts()
  const selectedLayout = useTrackLayout(layoutId || undefined)

  const defaultLapA = laps?.[0]?.number || 0
  const defaultLapB = laps?.[Math.min(1, (laps?.length || 1) - 1)]?.number || defaultLapA
  const selectedLapA = laps?.some((lap) => lap.number === lapA) ? lapA : defaultLapA
  const selectedLapB = laps?.some((lap) => lap.number === lapB) ? lapB : defaultLapB
  const telemetryA = useLapTelemetry(selectedSessionId, selectedLapA)
  const telemetryB = useLapTelemetry(selectedSessionId, selectedLapB)
  const lapComparison = useLapComparison(selectedSessionId, selectedLapA, selectedLapB)
  const selectedLapARecord = laps?.find((lap) => lap.number === selectedLapA)
  const selectedLapBRecord = laps?.find((lap) => lap.number === selectedLapB)
  const replayA = telemetryA.data && selectedLapARecord
    ? createPlaybackTrajectory(telemetryA.data, selectedLapARecord.time)
    : { trajectory: null, warning: null }
  const replayB = telemetryB.data && selectedLapBRecord
    ? createPlaybackTrajectory(telemetryB.data, selectedLapBRecord.time)
    : { trajectory: null, warning: null }
  const playbackDurationMs = Math.max(replayA.trajectory?.durationMs || 0, replayB.trajectory?.durationMs || 0)
  const playbackA = replayA.trajectory ? positionAtElapsed(replayA.trajectory, playbackTimeMs) : null
  const playbackB = replayB.trajectory ? positionAtElapsed(replayB.trajectory, playbackTimeMs) : null

  useEffect(() => {
    setPlaybackTimeMs(0)
    setIsPlaying(false)
  }, [selectedSessionId, selectedLapA, selectedLapB])

  useEffect(() => {
    if (!isPlaying || playbackDurationMs === 0) return
    const timer = window.setInterval(() => {
      setPlaybackTimeMs((current) => {
        const next = Math.min(current + 50 * playbackSpeed, playbackDurationMs)
        if (next === playbackDurationMs) setIsPlaying(false)
        return next
      })
    }, 50)
    return () => window.clearInterval(timer)
  }, [isPlaying, playbackDurationMs, playbackSpeed])

  const datasets = telemetryA.data && telemetryB.data ? [
    { data: telemetryA.data, color: '#f97316', label: `Lap A — #${selectedLapA}` },
    { data: telemetryB.data, color: '#2563eb', label: `Lap B — #${selectedLapB}` },
  ] : []
  const formatLapTime = (milliseconds: number) => {
    const minutes = Math.floor(milliseconds / 60_000)
    const seconds = (Math.floor(milliseconds / 1_000) % 60).toString().padStart(2, '0')
    const millis = (milliseconds % 1_000).toString().padStart(3, '0')
    return `${minutes}:${seconds}.${millis}`
  }
  const formatCarClass = (carClass: string) => `Group ${carClass.replace(/^[^A-Za-z0-9]+/, '')}`
  const formatDelta = (milliseconds: number) => `${milliseconds >= 0 ? '+' : '−'}${(Math.abs(milliseconds) / 1_000).toFixed(3)} s`
  const formatReplayTime = (milliseconds: number) => {
    const totalMilliseconds = Math.max(0, Math.round(milliseconds))
    const minutes = Math.floor(totalMilliseconds / 60_000).toString().padStart(2, '0')
    const seconds = Math.floor(totalMilliseconds / 1_000 % 60).toString().padStart(2, '0')
    const millis = (totalMilliseconds % 1_000).toString().padStart(3, '0')
    return `${minutes}:${seconds}.${millis}`
  }
  const formatDistance = (distance: number | null) => distance === null ? 'distance unavailable' : `${distance.toFixed(1)} m`
  const trajectoryDatasets = [
    ...datasets,
    ...(playbackA ? [{ data: [playbackA.point], color: '#ea580c', label: 'Lap A playback', pointRadius: 7, borderWidth: 0, showLine: false }] : []),
    ...(playbackB ? [{ data: [playbackB.point], color: '#1d4ed8', label: 'Lap B playback', pointRadius: 7, borderWidth: 0, showLine: false }] : []),
  ]

  if (sessionsLoading) return <main style={{ padding: 24 }}>Loading recorded sessions… <a href="/live">Open Live DDU</a></main>
  if (sessionsError) return <main style={{ padding: 24 }}>Unable to load sessions. Is the API running on port 8000? <a href="/live">Open Live DDU</a></main>
  if (!sessions?.length) return <main style={{ padding: 24 }}>No recorded sessions found yet. <a href="/live">Open Live DDU</a></main>

  return (
    <main style={{ maxWidth: 1100, margin: '0 auto', padding: 24, fontFamily: 'system-ui, sans-serif' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16 }}>
        <h1>GT7 Telemetry</h1>
        <a href="/live" style={{ color: '#ea580c', fontWeight: 700 }}>Open Live DDU →</a>
      </div>
      <p>Compare two recorded laps. Orange is Lap A; blue is Lap B.</p>

      <section style={{ display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'end', padding: 16, background: '#f3f4f6', borderRadius: 8 }}>
        <label>Session<br />
          <select value={selectedSessionId} onChange={(event) => setSessionId(event.target.value)}>
            {sessions.map((session) => <option value={session.id} key={session.id}>
              {new Date(session.end_ts * 1000).toLocaleString()} — {session.id.slice(0, 8)}
            </option>)}
          </select>
        </label>
        <label>Lap A<br />
          <select value={selectedLapA} onChange={(event) => setLapA(Number(event.target.value))} disabled={!laps?.length}>
            {laps?.map((lap) => <option value={lap.number} key={lap.id}>Lap {lap.number}</option>)}
          </select>
        </label>
        <label>Lap B<br />
          <select value={selectedLapB} onChange={(event) => setLapB(Number(event.target.value))} disabled={!laps?.length}>
            {laps?.map((lap) => <option value={lap.number} key={lap.id}>Lap {lap.number}</option>)}
          </select>
        </label>
        <label>Track layout (manual)<br />
          <select value={layoutId} onChange={(event) => setLayoutId(event.target.value)}>
            <option value="">No layout overlay</option>
            {trackLayouts.data?.map((layout) => <option value={layout} key={layout}>{layout}</option>)}
          </select>
        </label>
      </section>

      {sessionDetail.data && <section style={{ marginTop: 16, padding: 16, border: '1px solid #e5e7eb', borderRadius: 8 }}>
        <h2 style={{ marginTop: 0 }}>Session details</h2>
        <dl style={{ display: 'grid', gridTemplateColumns: 'max-content 1fr', gap: '6px 16px', margin: 0 }}>
          <dt>Date and time</dt><dd>{new Date(sessionDetail.data.session.end_ts * 1000).toLocaleString()}</dd>
          <dt>Best lap</dt><dd>{formatLapTime(sessionDetail.data.session.best_lap_time)}</dd>
          <dt>Recorded laps</dt><dd>{sessionDetail.data.lap_count}</dd>
          <dt>Car ID</dt><dd>{sessionDetail.data.session.car_id}</dd>
          <dt>Track</dt><dd>{sessionDetail.data.track?.name || 'Track not recorded'}</dd>
        </dl>
        {sessionDetail.data.car ? <>
          <h3>{sessionDetail.data.car.name}</h3>
          <p style={{ marginBottom: 0 }}>
            {sessionDetail.data.car.power} hp · {sessionDetail.data.car.torque} Nm · {sessionDetail.data.car.weight} kg · {sessionDetail.data.car.length} × {sessionDetail.data.car.width} × {sessionDetail.data.car.height} mm · {sessionDetail.data.car.train} · {formatCarClass(sessionDetail.data.car.class_)}
          </p>
        </> : <p style={{ marginBottom: 0 }}>This GT7 car ID is not catalogued locally yet; its real recorded ID is still shown above.</p>}
      </section>}
      {sessionDetail.isError && <p>Unable to load the session details.</p>}

      {(lapsLoading || telemetryA.isLoading || telemetryB.isLoading) && <p>Loading lap telemetry…</p>}
      {lapsError && <p>Unable to load laps for this session.</p>}
      {(telemetryA.isError || telemetryB.isError) && <p>Unable to load telemetry for one of the selected laps.</p>}
      {datasets.length > 0 && <section style={{ marginTop: 24 }}>
        <article style={{ marginBottom: 24, padding: 12, border: '1px solid #e5e7eb', borderRadius: 8 }}>
          <h2 style={{ fontSize: '1rem', margin: '0 0 8px' }}>Linked telemetry explorer</h2>
          <p>Pan, wheel zoom, box zoom, and reset synchronize all plots on physical lap distance. Orange is Lap A; blue is Lap B.</p>
          {lapComparison.isLoading && <p>Aligning laps by physical distance…</p>}
          {lapComparison.isError && <p>Unable to calculate the distance-aligned comparison.</p>}
          {lapComparison.data?.available && lapComparison.data.points && <>
            <p>{lapComparison.data.sign_convention}</p>
            <p>
              Lap A: {formatLapTime(lapComparison.data.lap_a_time_ms)} · Lap B: {formatLapTime(lapComparison.data.lap_b_time_ms)} · Final delta: {formatDelta(lapComparison.data.final_delta_ms || 0)}
            </p>
          </>}
          {lapComparison.data && !lapComparison.data.available && <p style={{ color: '#b91c1c' }}>
            Delta unavailable: {lapComparison.data.warning} Lap times are still shown: A {formatLapTime(lapComparison.data.lap_a_time_ms)}, B {formatLapTime(lapComparison.data.lap_b_time_ms)}.
          </p>}
          <BokehTelemetryExplorer
            lapA={telemetryA.data || []}
            lapB={telemetryB.data || []}
            lapATimeMs={selectedLapARecord?.time || 0}
            lapBTimeMs={selectedLapBRecord?.time || 0}
            comparison={lapComparison.data}
          />
        </article>
        <article style={{ marginBottom: 24, padding: 12, border: '1px solid #e5e7eb', borderRadius: 8 }}>
          <h2 style={{ fontSize: '1rem', margin: '0 0 8px' }}>Track and lap trajectory</h2>
          <p style={{ marginTop: 0 }}>Playback uses each lap’s recorded duration and raw captured sample order. It is a replay aid, not delta alignment or coaching.</p>
          {(replayA.warning || replayB.warning) && <p style={{ color: '#b91c1c' }}>
            Playback unavailable: {[replayA.warning, replayB.warning].filter(Boolean).join(' ')}
          </p>}
          {playbackDurationMs > 0 && <section style={{ display: 'grid', gap: 8, marginBottom: 12, padding: 12, background: '#f3f4f6', borderRadius: 8 }}>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
              <button type="button" onClick={() => setIsPlaying((playing) => !playing)}>{isPlaying ? 'Pause' : 'Play'}</button>
              <button type="button" onClick={() => { setIsPlaying(false); setPlaybackTimeMs(0) }}>Reset</button>
              <label>Speed <select value={playbackSpeed} onChange={(event) => setPlaybackSpeed(Number(event.target.value))}>
                <option value={1}>1×</option><option value={2}>2×</option><option value={4}>4×</option><option value={10}>10×</option>
              </select></label>
            </div>
            <input
              aria-label="Playback timeline"
              type="range"
              min="0"
              max={playbackDurationMs}
              step="50"
              value={playbackTimeMs}
              onChange={(event) => { setIsPlaying(false); setPlaybackTimeMs(Number(event.target.value)) }}
            />
            <div>Timeline: {formatReplayTime(playbackTimeMs)} / {formatReplayTime(playbackDurationMs)}</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16 }}>
              <span style={{ color: '#ea580c' }}>Lap A: {playbackA ? `${formatReplayTime(playbackA.elapsedMs)} · ${formatDistance(playbackA.distance)}` : 'trajectory unavailable'}</span>
              <span style={{ color: '#1d4ed8' }}>Lap B: {playbackB ? `${formatReplayTime(playbackB.elapsedMs)} · ${formatDistance(playbackB.distance)}` : 'trajectory unavailable'}</span>
            </div>
          </section>}
          {layoutId && <p style={{ marginTop: 0 }}>The {layoutId} layout was selected manually and is not inferred from this session.</p>}
          {selectedLayout.isLoading && <p>Loading selected track layout…</p>}
          {selectedLayout.isError && <p>Unable to load the selected track layout.</p>}
          {!selectedLayout.isLoading && <div style={{ height: 520 }}>
            <TrajectoryGraph datasets={trajectoryDatasets} trackLayout={selectedLayout.data} />
          </div>}
        </article>
        <article style={{ marginBottom: 24, padding: 12, border: '1px solid #e5e7eb', borderRadius: 8 }}>
          <h2 style={{ fontSize: '1rem', margin: '0 0 8px' }}>Input-state racing lines</h2>
          <p>Green = throttle ≥10%; red = brake ≥10%; purple = coasting. Lap A is solid; Lap B is lighter. Sparse labels mark braking starts (B), minimum-speed/apex vicinity (A), and throttle resumptions (T), followed by speed in km/h. Hover a segment for captured point data.</p>
          <RaceLineMap lapA={telemetryA.data || []} lapB={telemetryB.data || []} lapATimeMs={selectedLapARecord?.time || 0} lapBTimeMs={selectedLapBRecord?.time || 0} />
          {!lapComparison.data?.available && <p>Pairwise braking-distance measurements are unavailable until the distance-aligned comparison validates both laps.</p>}
        </article>
      </section>}
    </main>
  )
}

export default App
