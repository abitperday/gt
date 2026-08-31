import { useQuery } from '@tanstack/react-query'
import {getLapComparison, getLapTelemetry, getSessionDetail, getSessionLaps, getTrackLayout, getTrackLayouts, getSessionsList} from './index'

export const useLapTelemetry = (raceId: string, lapNumber: number) => {
    const {data, isLoading, isError} = useQuery({
        queryKey: ['lap', raceId, lapNumber],
        queryFn: () => getLapTelemetry(raceId, lapNumber),
        refetchOnWindowFocus: false,
        staleTime: 300,
        enabled: !!raceId && !!lapNumber
    })

    return {data, isLoading, isError}
}

export const useLapComparison = (raceId: string, lapA: number, lapB: number) => {
    const {data, isLoading, isError} = useQuery({
        queryKey: ['lap-comparison', raceId, lapA, lapB],
        queryFn: () => getLapComparison(raceId, lapA, lapB),
        refetchOnWindowFocus: false,
        staleTime: 300,
        enabled: !!raceId && !!lapA && !!lapB,
    })

    return {data, isLoading, isError}
}

export const useSessions = () => {
    const {data, isLoading, isError} = useQuery({
        queryKey: ['sessions'],
        queryFn: getSessionsList,
        refetchOnWindowFocus: false,
        staleTime: 300,
    })

    return {data, isLoading, isError}
}

export const useSessionLaps = (sId: string) => {
    const {data, isLoading, isError} = useQuery({
        queryKey: ['session-laps', sId],
        queryFn: () => getSessionLaps(sId),
        refetchOnWindowFocus: false,
        staleTime: 300,
        enabled: !!sId,
    })

    return {data, isLoading, isError}
}

export const useSessionDetail = (sId: string) => {
    const {data, isLoading, isError} = useQuery({
        queryKey: ['session', sId],
        queryFn: () => getSessionDetail(sId),
        refetchOnWindowFocus: false,
        staleTime: 300,
        enabled: !!sId,
    })

    return {data, isLoading, isError}
}

export const useTrackLayout = (trackName?: string) => {
    const {data, isLoading, isError} = useQuery({
        queryKey: ['track', trackName],
        queryFn: () => getTrackLayout(trackName as string),
        refetchOnWindowFocus: false,
        staleTime: 300,
        enabled: !!trackName,
    })

    return {data, isLoading, isError}
}

export const useTrackLayouts = () => {
    const {data, isLoading, isError} = useQuery({
        queryKey: ['track-layouts'],
        queryFn: getTrackLayouts,
        refetchOnWindowFocus: false,
        staleTime: 300,
    })

    return {data, isLoading, isError}
}
