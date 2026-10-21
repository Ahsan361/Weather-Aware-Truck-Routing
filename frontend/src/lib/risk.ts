import type { RiskLevel } from "../api/types"

export const RISK_LEVELS: RiskLevel[] = [0, 1, 2, 3, 4]

export const RISK_LABELS = ['Low', 'Moderate', 'High', 'Severe', 'No Travel'] as const

// green to purple, so "No Travel" does not look like just another shade of red
export const RISK_COLORS = ['#2f9e44', '#f2c200', '#f08c00', '#e03131', '#6a1b9a'] as const

export function riskLabel(level: number): string {
  return RISK_LABELS[level]
}

export function riskColor(level: number): string {
  return RISK_COLORS[level]
}

export const FACTOR_LABELS = { wind: 'Wind', rain: 'Rain', snow: 'Snow' } as const
