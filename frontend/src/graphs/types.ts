import type { TrackLayout } from "../api/schema"

export interface Dataset {
    label?: string,
    data: Record<string, number>[]
    color: string,
    pointRadius?: number,
    borderWidth?: number,
    showLine?: boolean,
}

interface Bound {
    min?: number
    max?: number
}

export interface Bounds {
    x?: Bound
    y?: Bound
}

export interface TrajectoryGraphProps {
    datasets: Array<Dataset>
    trackLayout?: TrackLayout,
    bounds?: Bounds
}

export interface StatGraphProps extends TrajectoryGraphProps {
    param: string
}

export interface BaseGraphProps extends TrajectoryGraphProps {
    title: string
    xKey: string,
    yKey: string
    aspectRatio?: number
    showGrid?: boolean
}
