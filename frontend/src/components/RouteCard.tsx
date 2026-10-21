import type { Route } from '../api/types'
import { formatDateTime, formatDuration, formatMiles } from '../lib/format'
import { RISK_COLORS, RISK_LABELS, riskColor, riskLabel } from '../lib/risk'
import styles from './RouteCard.module.css'

interface Props {
  route: Route
  routeCount: number
  timeZone: string
  selected: boolean
  onSelect: () => void
}

export function RouteCard({ route, routeCount, timeZone, selected, onSelect }: Props) {
  const { summary } = route
  const total = summary.miles_by_level.reduce((sum, miles) => sum + miles, 0) || 1

  // only the levels the route actually spends time in, worst first
  const exposure = summary.miles_by_level
    .map((miles, level) => ({ miles, level }))
    .filter(({ miles }) => miles >= 0.5)
    .reverse()
    .filter(({ level }) => level > 0)

  return (
    <article className={selected ? `${styles.card} ${styles.selected}` : styles.card}>
      <button type="button" className={styles.button} onClick={onSelect} aria-pressed={selected}>
        <header className={styles.header}>
          <h3>Route {route.id + 1}</h3>
          {route.recommended ? (
            <span className={styles.recommended}>Recommended</span>
          ) : (
            <span className={styles.rank}>
              #{route.rank} of {routeCount}
            </span>
          )}
        </header>

        <p className={styles.facts}>
          <strong>{formatDuration(route.duration_minutes)}</strong>
          <span>{formatMiles(route.distance_miles)}</span>
          <span>Arrives {formatDateTime(route.arrival, timeZone)}</span>
        </p>

        <div
          className={styles.bar}
          role="img"
          aria-label={`Weather along the route: ${summary.miles_by_level
            .map((miles, level) => `${Math.round(miles)} miles ${RISK_LABELS[level]}`)
            .join(', ')}`}
        >
          {summary.miles_by_level.map((miles, level) =>
            miles > 0 ? (
              <span
                key={level}
                style={{ width: `${(miles / total) * 100}%`, background: RISK_COLORS[level] }}
                title={`${RISK_LABELS[level]}: ${Math.round(miles)} mi`}
              />
            ) : null,
          )}
        </div>

        <p className={styles.summary}>
          <span className={styles.worst}>
            <span className={styles.dot} style={{ background: riskColor(summary.worst_level) }} aria-hidden="true" />
            Worst: {riskLabel(summary.worst_level)}
          </span>
          <span>Avg risk {summary.avg_risk.toFixed(2)} / 4</span>
        </p>

        {exposure.length > 0 && (
          <p className={styles.exposure}>
            {exposure.map(({ miles, level }) => `${riskLabel(level)} ${Math.round(miles)} mi`).join(' · ')}
          </p>
        )}
      </button>
    </article>
  )
}
