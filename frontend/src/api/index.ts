import axios from "axios";
import { type Session, type Car, type Track, type TrackLayout, type Lap, type LapComparison, type SessionDetail } from "./schema";

const apiClient = axios.create({
    baseURL: 'http://localhost:8000',
    timeout: 5000,
    headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    },
});

export const getCars = () => apiClient.get<Array<Car>>('/cars')
    .then(({data}) => data)

export const getTracks = () => apiClient.get<Array<Track>>('/tracks')
    .then(({data}) => data)

export const getSessionsList = () => apiClient.get<Array<Session>>('/sessions')
    .then(({data}) => data)

export const getSessionLaps = (sId: string) => apiClient.get<Lap[]>(`/sessions/${sId}/laps`)
    .then(({data}) => data)

export const getSessionDetail = (sId: string) => apiClient.get<SessionDetail>(`/sessions/${sId}`)
    .then(({data}) => data)

export const getLapTelemetry = (sId: string, lapNumber: number) => apiClient.get<Record<string, number>[]>(`/sessions/${sId}/laps/${lapNumber}`)
    .then(({data}) => data)

export const getLapComparison = (sId: string, lapA: number, lapB: number) => apiClient.get<LapComparison>(`/sessions/${sId}/compare`, {
    params: { lapA, lapB },
}).then(({data}) => data)

export const getTrackLayout = (trackName: string) => apiClient.get<TrackLayout>((`layouts/${trackName}`))
    .then(({data}) => data)

export const getTrackLayouts = () => apiClient.get<string[]>('/layouts')
    .then(({data}) => data)
