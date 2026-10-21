import { memo } from 'react'
import type { AnalyzeResponse } from '../api/types'
import { CheckpointList } from './CheckpointList'
import { RouteCard } from './RouteCard'
import styles from './ResultsPanel.module.css'

interface Props {
  result: AnalyzeResponse
  selectedRouteId: number | null
  focusedCheckpoint: number | null
  onSelectRoute: (routeId: number) => void
  onFocusCheckpoint: (index: number) => void
}

function ResultsPanelView({ result, selectedRouteId, focusedCheckpoint, onSelectRoute, onFocusCheckpoint }: Props) {
  const timeZone = result.origin.timezone
  const ordered = [...result.routes].sort((a, b) => a.rank - b.rank)
  const selected = result.routes.find((route) => route.id === selectedRouteId)
  const best = result.routes.find((route) => route.id === result.recommendation.route_id)

  return (
    <div className={styles.panel}>
      <section className={styles.banner} aria-label="Recommendation">
        <h2>Take Route {(best?.id ?? 0) + 1}</h2>
        <p>{result.recommendation.reason}</p>
        {result.routes.length < 3 && (
          <p className={styles.note}>
            Only {result.routes.length} sensible {result.routes.length === 1 ? 'route' : 'routes'} found for this trip.
          </p>
        )}
      </section>

      <div className={styles.cards}>
        {ordered.map((route) => (
          <RouteCard
            key={route.id}
            route={route}
            routeCount={result.routes.length}
            timeZone={timeZone}
            selected={route.id === selectedRouteId}
            onSelect={() => onSelectRoute(route.id)}
          />
        ))}
      </div>

      {selected && (
        <CheckpointList
          key={selected.id}
          route={selected}
          timeZone={timeZone}
          focused={focusedCheckpoint}
          onFocus={onFocusCheckpoint}
        />
      )}

      <p className={styles.footnote}>
        Times are in the starting point's time zone. ETAs are driving time only and don't include rest breaks.
      </p>
    </div>
  )
}

export const ResultsPanel = memo(ResultsPanelView)
