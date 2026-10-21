import type { Checkpoint, RiskLevel } from '../api/types'
import { formatDateTime, timeZoneAbbreviation } from '../lib/format'
import { FACTOR_LABELS, riskColor, riskLabel } from '../lib/risk'
import styles from './checkpointPopup.module.css'

function element(tag: string, className?: string, text?: string): HTMLElement {
  const node = document.createElement(tag)
  if (className) node.className = className
  if (text !== undefined) node.textContent = text
  return node
}

function riskBadge(level: RiskLevel): HTMLElement {
  const badge = element('span', styles.badge)
  const dot = element('span', styles.dot)
  dot.style.background = riskColor(level)
  badge.append(dot, riskLabel(level))
  return badge
}

/** Built with the DOM API rather than HTML strings, so nothing here can inject markup. */
export function buildCheckpointPopup(checkpoint: Checkpoint, timeZone: string): HTMLElement {
  const { weather, risk } = checkpoint
  const root = element('div', styles.popup)

  const header = element('div', styles.header)
  header.append(riskBadge(risk.level), element('span', styles.mile, `Mile ${Math.round(checkpoint.mile)}`))

  const when = `${formatDateTime(checkpoint.eta, timeZone)} ${timeZoneAbbreviation(checkpoint.eta, timeZone)}`

  const rows = element('div', styles.rows)
  const addRow = (name: string, value: string, level: RiskLevel) => {
    rows.append(element('span', styles.name, name), element('span', styles.value, value), riskBadge(level))
  }
  addRow('Wind', `${weather.wind_mph.toFixed(0)} mph`, risk.wind)
  addRow('Rain', `${weather.rain_in_hr.toFixed(2)} in/hr`, risk.rain)
  addRow('Snow', `${weather.snow_in_hr.toFixed(2)} in/hr`, risk.snow)

  root.append(header, element('p', styles.eta, `Arrives ${when}`), rows)
  if (risk.factor && risk.level > 0) {
    root.append(element('p', styles.note, `Mostly because of ${FACTOR_LABELS[risk.factor].toLowerCase()}.`))
  }
  return root
}
