import { RISK_COLORS, RISK_LABELS } from '../lib/risk'
import styles from './RiskLegend.module.css'

export function RiskLegend() {
  return (
    <ul className={styles.legend} aria-label="Risk levels">
      {RISK_LABELS.map((label, level) => (
        <li key={label}>
          <span className={styles.swatch} style={{ background: RISK_COLORS[level] }} aria-hidden="true" />
          {label}
        </li>
      ))}
    </ul>
  )
}
