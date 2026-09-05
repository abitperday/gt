import type { CSSProperties } from 'react'
import './InstrumentGauges.css'

const finite = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value)

function dialPoint(angle: number, radius: number, cx: number, cy: number) {
  const radians = angle * Math.PI / 180
  return { x: cx + Math.sin(radians) * radius, y: cy - Math.cos(radians) * radius }
}

function FuelPump() {
  return <g fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M-7 8V-8h11V8M-9 8H6M-5-5h7v5h-7zM4-4h2l3 3v6c0 2 3 2 3 0v-9L8-8M9-7v4h3" />
  </g>
}

function TurboIcon() {
  return <g fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M-10-8h9a9 9 0 0 1 9 9v4h5M9 10H0a9 9 0 0 1 0-18M-9-1h-4" />
    <circle cx="0" cy="1" r="4.5" />
    <path d="M0-3.5V5.5M-4.5 1h9M-3.2-2.2l6.4 6.4M3.2-2.2l-6.4 6.4" />
  </g>
}

export function FuelGauge({ fuelLitres, capacityLitres }: { fuelLitres?: number | null, capacityLitres?: number | null }) {
  const validFuel = finite(fuelLitres) && fuelLitres >= 0
  const percentage = validFuel && finite(capacityLitres) && capacityLitres > 0
    ? Math.max(0, Math.min(100, fuelLitres / capacityLitres * 100))
    : null
  const state = percentage === null ? 'unknown' : percentage <= 10 ? 'low' : percentage <= 30 ? 'reserve' : 'normal'
  const label = state === 'low' ? 'LOW FUEL' : state === 'reserve' ? 'RESERVE' : 'FUEL'
  const reading = validFuel ? fuelLitres.toFixed(1) : '—'
  const description = percentage === null
    ? `Fuel: ${validFuel ? `${reading} litres, ` : ''}level unavailable`
    : `Fuel: ${reading} litres, ${Math.round(percentage)} percent${state === 'low' ? ', low fuel' : state === 'reserve' ? ', reserve' : ''}`

  return <section className={`instrument-fuel instrument-fuel--${state}`} aria-label={description}>
    <div className="instrument-fuel__heading">
      <span className="instrument-fuel__label">{label}</span>
      <div className="instrument-fuel__reading"><strong>{reading}<small>L</small></strong><span>{percentage === null ? '—%' : `${percentage.toFixed(0)}%`}</span></div>
    </div>
    <svg className="instrument-fuel__dial" viewBox="0 0 200 111" aria-hidden="true">
      <path className="instrument-fuel__arc" d="M29.52 63.35A75 75 0 0 1 170.48 63.35" />
      <path className="instrument-fuel__edge" d="M22.95 60.95A82 82 0 0 1 177.05 60.95" />
      {Array.from({ length: 21 }, (_, index) => {
        const major = index % 5 === 0
        const angle = -70 + index * 7
        const from = dialPoint(angle, major ? 68 : 73, 100, 89)
        const to = dialPoint(angle, 82, 100, 89)
        return <line key={index} className={major ? 'instrument-fuel__tick instrument-fuel__tick--major' : 'instrument-fuel__tick'} x1={from.x} y1={from.y} x2={to.x} y2={to.y} />
      })}
      <text className="instrument-fuel__end" x="24" y="86">E</text>
      <text className="instrument-fuel__end" x="176" y="86">F</text>
      {percentage !== null && <g className="instrument-fuel__needle" style={{ transform: `rotate(${-70 + percentage * 1.4}deg)` }}>
        <path d="M98.4 90 99.45 20 100.55 20 101.6 90Z" />
      </g>}
      <circle className="instrument-fuel__hub" cx="100" cy="89" r="4.6" />
      <g className="instrument-fuel__pump" transform="translate(100 102) scale(.85)"><FuelPump /></g>
    </svg>
    {percentage === null && <small className="instrument-fuel__unavailable">LEVEL UNAVAILABLE</small>}
  </section>
}

export function TurboGauge({ boost }: { boost?: number | null }) {
  const pressure = finite(boost) ? boost : null
  // GT7 boost is relative pressure in bar. The face uses x100 kPa (1 bar).
  const angle = pressure === null ? 0 : (Math.max(-1, Math.min(2, pressure)) - 1) * 90
  const needleStyle = { '--turbo-initial-angle': `${angle}deg` } as CSSProperties

  return <section className="instrument-turbo" aria-label="Turbocharger boost pressure">
    <svg className="instrument-turbo__dial" viewBox="0 0 144 144" aria-hidden="true">
      <path className="instrument-turbo__arc" d="M68 117A49 49 0 1 1 117 68" />
      <path className="instrument-turbo__positive-arc" d="M19 68A49 49 0 0 1 117 68" />
      {Array.from({ length: 31 }, (_, index) => {
        const major = index % 10 === 0
        const angle = -180 + index * 9
        const from = dialPoint(angle, major ? 39 : index % 5 === 0 ? 43 : 46, 68, 68)
        const to = dialPoint(angle, 50, 68, 68)
        return <line key={index} className={major ? 'instrument-turbo__tick instrument-turbo__tick--major' : 'instrument-turbo__tick'} x1={from.x} y1={from.y} x2={to.x} y2={to.y} />
      })}
      <text className="instrument-turbo__number" x="68" y="135">−1</text>
      <text className="instrument-turbo__number" x="7" y="73">0</text>
      <text className="instrument-turbo__number" x="68" y="10">1</text>
      <text className="instrument-turbo__number" x="131" y="73">2</text>
      <g className="instrument-turbo__icon" transform="translate(88 85) scale(.75)"><TurboIcon /></g>
      <text className="instrument-turbo__unit" x="99" y="108">×100</text>
      <text className="instrument-turbo__unit" x="99" y="121">kPa</text>
      {pressure !== null && <g className="instrument-turbo__needle" style={needleStyle}>
        <path d="M66.7 73 67.5 23 68.5 23 69.3 73Z" />
      </g>}
      <circle className="instrument-turbo__hub" cx="68" cy="68" r="4" />
    </svg>
    <div className="instrument-turbo__reading">
      <span className="instrument-turbo__label">TC</span>
      <span className="instrument-turbo__caption">TURBO</span>
      <strong data-live="turbo-pressure">{pressure === null ? '—' : (pressure * 100).toFixed(0)}</strong>
      <small>kPa</small>
    </div>
  </section>
}
