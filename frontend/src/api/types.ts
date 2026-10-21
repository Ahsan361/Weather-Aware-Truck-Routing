export type RiskLevel = 0 | 1 | 2 | 3 | 4
export type IntervalMiles = 10 | 25 | 50

export interface Place {
  label: string
  lat: number
  lon: number
}

export interface AnalyzeRequest {
  origin: Place
  destination: Place
  departure: string
  load_lb: number
  interval_miles: IntervalMiles
}

export interface CheckpointWeather {
  wind_mph: number
  rain_in_hr: number
  snow_in_hr: number
}

export interface CheckpointRisk {
  level: RiskLevel
  factor: 'wind' | 'rain' | 'snow' | null
  wind: RiskLevel
  rain: RiskLevel
  snow: RiskLevel
}

export interface Checkpoint {
  mile: number
  lat: number
  lon: number
  eta: string
  weather: CheckpointWeather
  risk: CheckpointRisk
}

export interface RouteSegment {
  level: RiskLevel
  coordinates: [number, number][]
}

export interface RouteSummary {
  miles_by_level: number[]
  avg_risk: number
  worst_level: RiskLevel
}

export interface Route {
  id: number
  rank: number
  recommended: boolean
  distance_miles: number
  duration_minutes: number
  arrival: string
  summary: RouteSummary
  segments: RouteSegment[]
  checkpoints: Checkpoint[]
}

export interface HeatmapPoint {
  lat: number
  lon: number
  levels: RiskLevel[]
}

export interface Heatmap {
  start: string
  hours: number
  points: HeatmapPoint[]
}

export interface AnalyzeResponse {
  departure: string
  load_lb: number
  interval_miles: IntervalMiles
  origin: Place & { timezone: string }
  destination: Place
  recommendation: { route_id: number; reason: string }
  routes: Route[]
  heatmap: Heatmap
}
