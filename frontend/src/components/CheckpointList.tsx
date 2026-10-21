import { useEffect, useRef } from 'react'
import type { Checkpoint, Route } from '../api/types'
import { formatDateTime } from '../lib/format'
import { FACTOR_LABELS, riskColor, riskLabel } from '../lib/risk'
import styles from './CheckpointList.module.css'

interface Props {
  route: Route
  timeZone: string
  focused: number | null
  onFocus: (index: number) => void
}

function detail(checkpoint: Checkpoint): string {
  const { risk, weather } = checkpoint
  if (!risk.factor) return 'Clear'
  if (risk.factor === 'wind') return `Wind ${weather.wind_mph.toFixed(0)} mph`
  const amount = risk.factor === 'rain' ? weather.rain_in_hr : weather.snow_in_hr
  return `${FACTOR_LABELS[risk.factor]} ${amount.toFixed(2)} in/hr`
}

export function CheckpointList({ route, timeZone, focused, onFocus }: Props) {
  const focusedRow = useRef<HTMLLIElement>(null)

  // a click on the map should bring the matching row into view
  useEffect(() => {
    focusedRow.current?.scrollIntoView({ block: 'nearest' })
  }, [focused])

  return (
    <details className={styles.details}>
      <summary>
        Checkpoints <span>({route.checkpoints.length})</span>
      </summary>
      <ol className={styles.list}>
        {route.checkpoints.map((checkpoint, index) => (
          <li key={index} ref={index === focused ? focusedRow : undefined}>
            <button
              type="button"
              className={index === focused ? `${styles.row} ${styles.focused}` : styles.row}
              onClick={() => onFocus(index)}
            >
              <span className={styles.mile}>Mile {Math.round(checkpoint.mile)}</span>
              <span className={styles.time}>{formatDateTime(checkpoint.eta, timeZone)}</span>
              <span className={styles.risk}>
                <span
                  className={styles.dot}
                  style={{ background: riskColor(checkpoint.risk.level) }}
                  aria-hidden="true"
                />
                {riskLabel(checkpoint.risk.level)}
              </span>
              <span className={styles.detail}>{detail(checkpoint)}</span>
            </button>
          </li>
        ))}
      </ol>
    </details>
  )
}
