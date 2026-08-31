import {Chart as ChartJS,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Legend,
  Tooltip,
} from 'chart.js'
import { Line } from 'react-chartjs-2'
import type { DeltaPoint } from '../api/schema'
import type { BaseGraphProps, StatGraphProps, TrajectoryGraphProps, Dataset, Bounds } from './types'

ChartJS.register(
  LinearScale,
  LineElement,
  PointElement,
  Title,
  Tooltip,
  Legend,
)

const BaseGraph: React.FC<BaseGraphProps> = ({datasets, xKey, yKey, title, aspectRatio, bounds, showGrid = true}) => {
  return (
    <>
      <Line
        width={500}
        height={500}
        data={{
          datasets: datasets.map(dataset => ({
            label: dataset.label,
            data: dataset.data,
            borderWidth: dataset.borderWidth ?? 1,
            backgroundColor: dataset.color,
            borderColor: dataset.color,
            fill: false,
            pointRadius: dataset.pointRadius ?? 0,
            showLine: dataset.showLine,
          }))
        }}
        options={{
          maintainAspectRatio: false,
          responsive: true,
          plugins: {
              title: {
                text: title,
                display: true,
              },
              legend: {
                labels: {
                  filter: (item) => !!item.text
                }
              },
              zoom: {
                zoom: {
                  wheel: {
                    enabled: true,
                  },
                  pinch: {
                    enabled: true,
                  },
                  mode: 'xy',
                },
                pan: {
                  enabled: true,
                  mode: 'xy',
                }
              }
          },
          parsing: {
            xAxisKey: xKey,
            yAxisKey: yKey,
          },
          scales: {
              x: {
                type: 'linear',
                min: bounds?.x?.min,
                max: bounds?.x?.max,
                border: {display: true},
                grid: {display: showGrid},
                ticks: {display: false},
              },
              y: {
                type: 'linear',
                min: bounds?.y?.min,
                max: bounds?.y?.max,
                border: {display: true},
                grid: {display: showGrid},
                ticks: {display: showGrid},
              },
          },
          aspectRatio
        }}
      />
    </>
  )
}

const TrajectoryGraph: React.FC<TrajectoryGraphProps> = ({datasets, trackLayout}) => {
  const coordinateKey = ['y', 'z'].find((key) => datasets.every((dataset) =>
    dataset.data.length > 0 && dataset.data.every((point) => Number.isFinite(point.x) && Number.isFinite(point[key]))
  ))

  if (!coordinateKey) {
    return <p>Trajectory is unavailable: the selected laps need x/y or x/z coordinates.</p>
  }

  const toPlotCoordinates = (data: Record<string, number>[]) => data.map((point) => ({
    ...point,
    plotX: point.x,
    plotY: point[coordinateKey],
  }))
  const plotDatasets: Dataset[] = datasets.map((dataset) => ({
    ...dataset,
    data: toPlotCoordinates(dataset.data),
  }))

  const getInitialBound = () => {
    // TODO: optimization
    const xData1 = plotDatasets[0].data.map(item => item.plotX)
    const yData1 = plotDatasets[0].data.map(item => item.plotY)

    const xData2 = plotDatasets[1].data.map(item => item.plotX)
    const yData2 = plotDatasets[1].data.map(item => item.plotY)

    const minXData1 = Math.min(...xData1)
    const maxXData1 = Math.max(...xData1)
    const minXData2 = Math.min(...xData2)
    const maxXData2 = Math.min(...xData2)

    const minYData1 = Math.min(...yData1)
    const maxYData1 = Math.max(...yData1)
    const minYData2 = Math.min(...yData2)
    const maxYData2 = Math.min(...yData2)

    const minX = Math.min(...[minXData1, minXData2])
    const maxX = Math.max(...[maxXData1, maxXData2])
    const minY = Math.min(...[minYData1, minYData2])
    const maxY = Math.max(...[maxYData1, maxYData2])

    return Math.max(...[Math.abs(minX), Math.abs(maxX), Math.abs(minY), Math.abs(maxY)]) * 1.1
  }

  const graphData: Dataset[] = trackLayout ? [
    ...plotDatasets,
    {
      data: toPlotCoordinates(trackLayout[0]),
      color: 'black'
    },
    {
      data: toPlotCoordinates(trackLayout[1]),
      color: 'black'
    }
  ] : plotDatasets

  const bound = getInitialBound()

  return (
    <BaseGraph 
        datasets={graphData}
        xKey='plotX'
        yKey='plotY'
        aspectRatio={1}
        bounds={{
          x: {
            min: -bound,
            max: bound,
          },
          y: {
            min: -bound,
            max: bound,
          },
        }}
        title='Trajectory'
        showGrid={false}
    />
  )
}

const StatGraph: React.FC<StatGraphProps> = ({datasets, param}) => {
  const getInitialBounds = (): Bounds => {
    const lastX1 = datasets[0].data[datasets[0].data.length - 1].dist
    const lastX2 = datasets[1].data[datasets[1].data.length - 1].dist

    const maxY1 = Math.max(
      ...datasets[0].data.map(item => item[param])
    )
    const maxY2 = Math.max(
      ...datasets[1].data.map(item => item[param])
    )

    return {
      x: {
        min: 0,
        max: Math.max(lastX1, lastX2)
      },
      y: {
        min: 0,
        max: Math.max(maxY1, maxY2) * 1.05
      }
    }
  }
  return (
    <div style={{height: '260px', width: '100%'}}>
      <BaseGraph 
        datasets={datasets}
        xKey='dist'
        yKey={param}
        title={param}
        bounds={getInitialBounds()}
      />
    </div>
  )
}

const DeltaGraph: React.FC<{points: DeltaPoint[]}> = ({points}) => {
  const plotPoints = points.map((point) => ({
    progress_percent: point.progress * 100,
    delta_ms: point.delta_ms,
  }))
  const deltas = plotPoints.map((point) => point.delta_ms)
  const magnitude = Math.max(...deltas.map(Math.abs), 1) * 1.1

  return (
    <div style={{height: '300px', width: '100%'}}>
      <BaseGraph
        datasets={[{data: plotPoints, color: '#7c3aed', label: 'A − B'}]}
        xKey='progress_percent'
        yKey='delta_ms'
        title='Cumulative delta time (ms)'
        bounds={{x: {min: 0, max: 100}, y: {min: -magnitude, max: magnitude}}}
      />
    </div>
  )
}

export {TrajectoryGraph, StatGraph, DeltaGraph}
