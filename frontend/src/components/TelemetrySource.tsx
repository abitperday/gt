import { useEffect } from "react"
import { useSessionLaps, useSessions } from "../api/hooks"

const toTimeStr = (ms: number): string => {
    if (ms < 0) return 'No Time'

    const millis = (ms % 1000).toString().padStart(3, '0')
    const minutes = Math.floor(ms / 60000)
    const seconds = (Math.floor(ms / 1000) % 60).toString().padStart(2, '0')

    return `${minutes}:${seconds}.${millis}`
}

interface TelemetrySourceProps {
    sId: string
    lapN: number
    setSId: React.Dispatch<React.SetStateAction<string>>
    setLapN: React.Dispatch<React.SetStateAction<number>>
}

const TelemetrySource: React.FC<TelemetrySourceProps> = ({sId, lapN, setSId, setLapN}) => {
    const {data, isLoading} = useSessions()
    const {data: laps} = useSessionLaps(sId)

    useEffect(() => {
        setLapN(() => laps? laps[0].number : 0)
    }, [sId, laps, setLapN])

    if (!data || isLoading) return <div>Loading...</div>

    return (
        <div>
            <div>
                <select value={sId} onChange={e => setSId(e.target.value)}>
                    {data.map(item => (
                        <option value={item.id} key={item.id}>
                            {(new Date(item.end_ts * 1000)).toISOString()}{' '}
                            ({toTimeStr(item.best_lap_time)})
                        </option>
                    ))}
                </select>
            </div>
            {!!laps && (
                <div>
                    <select value={lapN} onChange={e => setLapN(Number(e.target.value))}>
                        {laps.map(item => (
                            <option value={item.number} key={item.id}>
                                {item.number}{' '}
                                ({toTimeStr(item.time)})
                            </option>
                        ))}
                    </select>
                </div>
            )}
        </div>
    )
}

export default TelemetrySource
