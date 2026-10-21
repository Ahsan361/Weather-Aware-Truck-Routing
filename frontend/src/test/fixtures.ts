import type { AnalyzeResponse, Checkpoint, Route, RiskLevel } from '../api/types'

export function checkpoint(mile: number, level: RiskLevel = 0, overrides: Partial<Checkpoint> = {}): Checkpoint {
  return {
    mile,
    lat: 40 + mile / 1000,
    lon: -100 + mile / 100,
    eta: '2026-11-03T12:00:00Z',
    weather: { wind_mph: 12, rain_in_hr: 0, snow_in_hr: 0 },
    risk: { level, factor: level > 0 ? 'wind' : null, wind: level, rain: 0, snow: 0 },
    ...overrides,
  }
}

export function route(id: number, overrides: Partial<Route> = {}): Route {
  return {
    id,
    rank: id + 1,
    recommended: id === 0,
    distance_miles: 100,
    duration_minutes: 120,
    arrival: '2026-11-03T14:00:00Z',
    summary: { miles_by_level: [100, 0, 0, 0, 0], avg_risk: 0, worst_level: 0 },
    segments: [
      {
        level: 0,
        coordinates: [
          [-100 + id, 40],
          [-99 + id, 41],
        ],
      },
    ],
    checkpoints: [checkpoint(0), checkpoint(50), checkpoint(100)],
    ...overrides,
  }
}

export function analysis(overrides: Partial<AnalyzeResponse> = {}): AnalyzeResponse {
  return {
    departure: '2026-11-03T12:00:00Z',
    load_lb: 45_000,
    interval_miles: 25,
    origin: { label: 'Dallas, TX', lat: 32.78, lon: -96.8, timezone: 'America/Chicago' },
    destination: { label: 'Houston, TX', lat: 29.76, lon: -95.37 },
    recommendation: { route_id: 0, reason: 'Same weather exposure as the next best route, but 20 min faster.' },
    routes: [route(0), route(1)],
    heatmap: {
      start: '2026-11-03T12:00:00Z',
      hours: 2,
      points: [{ lat: 40, lon: -100, levels: [0, 2, 4] }],
    },
    ...overrides,
  }
}
