export interface Car {
    id: number
    name: string
    power: number
    torque: number
    weight: number
    length: number
    width: number
    height: number
    train: string
    class_: string
}

export interface Track {
    id: number
    name: string
    length: number
    num_turns: number
    country: string
}

export interface Session {
    id: string
    track_id: number | null
    car_id: number
    racer: string | null
    best_lap_time: number
    end_ts: number
}

export interface Lap {
    id: string
    number: number
    race_id: string
    time: number
}

export interface SessionDetail {
    session: Session
    lap_count: number
    car: Car | null
    track: Track | null
}

export interface DeltaPoint {
    progress: number
    elapsed_a_ms: number
    elapsed_b_ms: number
    delta_ms: number
}

export interface LapComparison {
    available: boolean
    warning: string | null
    lap_a_time_ms: number
    lap_b_time_ms: number
    points?: DeltaPoint[]
    final_delta_ms?: number
    sign_convention?: string
}

// interface Point {
//     x: number
//     y: number
//     z: number
// }
type Point = Record<string, number>

export type TrackLayout = [Array<Point>, Array<Point>]
