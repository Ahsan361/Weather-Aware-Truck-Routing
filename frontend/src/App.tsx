import { lazy, Suspense, useCallback, useRef, useState } from 'react'
import { useAnalyzeTrip } from './api/trips'
import type { AnalyzeRequest, AnalyzeResponse } from './api/types'
import styles from './App.module.css'
import { AnalysisProgress } from './components/AnalysisProgress'
import { ErrorNotice } from './components/ErrorNotice'
import { HeatmapControls } from './components/HeatmapControls'
import { ResultsPanel } from './components/ResultsPanel'
import { RiskLegend } from './components/RiskLegend'
import { TripForm } from './components/TripForm'

// MapLibre is most of the app's weight, so it loads in its own chunk while the form is already usable
const TripMap = lazy(() => import('./components/TripMap').then((module) => ({ default: module.TripMap })))

export default function App() {
  const analysis = useAnalyzeTrip()
  const lastRequest = useRef<AnalyzeRequest | null>(null)

  const [selectedRouteId, setSelectedRouteId] = useState<number | null>(null)
  const [focusedCheckpoint, setFocusedCheckpoint] = useState<number | null>(null)
  const [heatmapVisible, setHeatmapVisible] = useState(true)
  const [heatmapHour, setHeatmapHour] = useState(0)

  // kept in state rather than read from the mutation, so a failed or pending request
  // doesn't wipe the routes already on the map
  const [result, setResult] = useState<AnalyzeResponse | null>(null)

  const analyze = useCallback(
    (request: AnalyzeRequest) => {
      lastRequest.current = request
      analysis.mutate(request, {
        onSuccess: (data: AnalyzeResponse) => {
          setResult(data)
          setSelectedRouteId(data.recommendation.route_id)
          setFocusedCheckpoint(null)
          setHeatmapHour(0)
        },
      })
    },
    // mutate is stable between renders
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [analysis.mutate],
  )

  const selectRoute = useCallback((routeId: number) => {
    setSelectedRouteId(routeId)
    setFocusedCheckpoint(null)
  }, [])

  return (
    <div className={styles.app}>
      <aside className={styles.sidebar}>
        <header className={styles.brand}>
          <h1>Spotter</h1>
          <p>Weather-aware truck routing</p>
        </header>

        <TripForm pending={analysis.isPending} onSubmit={analyze} />

        <div className={styles.results}>
          {analysis.isPending && <AnalysisProgress />}

          {analysis.isError && !analysis.isPending && (
            <ErrorNotice
              message={analysis.error.message}
              onRetry={() => lastRequest.current && analyze(lastRequest.current)}
            />
          )}

          {result && !analysis.isPending && !analysis.isError && (
            <ResultsPanel
              result={result}
              selectedRouteId={selectedRouteId}
              focusedCheckpoint={focusedCheckpoint}
              onSelectRoute={selectRoute}
              onFocusCheckpoint={setFocusedCheckpoint}
            />
          )}

          {!result && !analysis.isPending && !analysis.isError && (
            <p className={styles.intro}>
              Enter a trip to compare up to three routes. Each one is checked against the forecast at the time the
              truck will actually be there, using your load weight.
            </p>
          )}
        </div>
      </aside>

      <main className={styles.mapArea}>
        <Suspense fallback={<div className={styles.mapPlaceholder} aria-hidden="true" />}>
          <TripMap
            result={result}
            selectedRouteId={selectedRouteId}
            focusedCheckpoint={focusedCheckpoint}
            heatmapVisible={heatmapVisible}
            heatmapHour={heatmapHour}
            onSelectRoute={selectRoute}
            onFocusCheckpoint={setFocusedCheckpoint}
          />
        </Suspense>
        {result && <RiskLegend />}
        {result && (
          <HeatmapControls
            visible={heatmapVisible}
            onVisibleChange={setHeatmapVisible}
            hour={heatmapHour}
            onHourChange={setHeatmapHour}
            maxHour={result.heatmap.hours}
            startIso={result.heatmap.start}
            timeZone={result.origin.timezone}
          />
        )}
      </main>
    </div>
  )
}
