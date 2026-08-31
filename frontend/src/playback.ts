export interface PlaybackSample {
  elapsedMs: number
  distance: number | null
  point: Record<string, number>
}

export interface PlaybackTrajectory {
  durationMs: number
  samples: PlaybackSample[]
}

export type PlaybackResult =
  | { trajectory: PlaybackTrajectory; warning: null }
  | { trajectory: null; warning: string }

const isFiniteNumber = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value)

export const createPlaybackTrajectory = (data: Record<string, number>[], durationMs: number): PlaybackResult => {
  if (!isFiniteNumber(durationMs) || durationMs <= 0) {
    return { trajectory: null, warning: 'This lap has no valid recorded duration.' }
  }
  if (data.length < 2) {
    return { trajectory: null, warning: 'This lap has too few captured trajectory samples.' }
  }

  const coordinateKey = ['y', 'z'].find((key) => data.filter((point) =>
    isFiniteNumber(point.x) && isFiniteNumber(point[key])
  ).length >= 2)
  if (!coordinateKey) {
    return { trajectory: null, warning: 'This lap has no valid x/y or x/z trajectory coordinates.' }
  }

  const samples = data.flatMap((point, index) => {
    if (!isFiniteNumber(point.x) || !isFiniteNumber(point[coordinateKey])) return []
    return [{
      elapsedMs: durationMs * index / (data.length - 1),
      distance: isFiniteNumber(point.dist) ? point.dist : null,
      point,
    }]
  })
  if (samples.length < 2) {
    return { trajectory: null, warning: 'This lap has too few valid trajectory samples.' }
  }
  return { trajectory: { durationMs, samples }, warning: null }
}

export const positionAtElapsed = (trajectory: PlaybackTrajectory, elapsedMs: number): PlaybackSample => {
  const clampedElapsed = Math.min(Math.max(elapsedMs, 0), trajectory.durationMs)
  const samples = trajectory.samples
  const rightIndex = samples.findIndex((sample) => sample.elapsedMs >= clampedElapsed)
  if (rightIndex <= 0) return samples[0]
  if (rightIndex === -1) return samples[samples.length - 1]

  const left = samples[rightIndex - 1]
  const right = samples[rightIndex]
  const fraction = (clampedElapsed - left.elapsedMs) / (right.elapsedMs - left.elapsedMs)
  const point: Record<string, number> = {}
  for (const key of ['x', 'y', 'z', 'dist']) {
    if (isFiniteNumber(left.point[key]) && isFiniteNumber(right.point[key])) {
      point[key] = left.point[key] + fraction * (right.point[key] - left.point[key])
    }
  }
  return {
    elapsedMs: clampedElapsed,
    distance: isFiniteNumber(point.dist) ? point.dist : left.distance,
    point,
  }
}
