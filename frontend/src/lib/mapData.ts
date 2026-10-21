import type { ExpressionSpecification } from 'maplibre-gl'
import type { Feature, FeatureCollection, LineString, Point } from 'geojson'
import type { Heatmap, Route } from '../api/types'
import { RISK_COLORS } from './risk'

export type LngLatBounds = [[number, number], [number, number]]

export function routeLines(routes: Route[]): FeatureCollection<LineString> {
  const features: Feature<LineString>[] = routes.flatMap((route) =>
    route.segments.map((segment) => ({
      type: 'Feature' as const,
      properties: { routeId: route.id, level: segment.level },
      geometry: { type: 'LineString' as const, coordinates: segment.coordinates },
    })),
  )
  return { type: 'FeatureCollection', features }
}

export function checkpointPoints(route: Route | undefined): FeatureCollection<Point> {
  const features: Feature<Point>[] = (route?.checkpoints ?? []).map((checkpoint, index) => ({
    type: 'Feature',
    properties: { index, level: checkpoint.risk.level },
    geometry: { type: 'Point', coordinates: [checkpoint.lon, checkpoint.lat] },
  }))
  return { type: 'FeatureCollection', features }
}

/**
 * One point per checkpoint location with the risk level for every hour stored as h0, h1, ...
 * Flat numeric properties let the slider just swap a paint expression, with no new data.
 */
export function heatmapPoints(heatmap: Heatmap): FeatureCollection<Point> {
  const features: Feature<Point>[] = heatmap.points.map((point) => {
    const properties: Record<string, number> = {}
    point.levels.forEach((level, hour) => {
      properties[`h${hour}`] = level
    })
    return {
      type: 'Feature',
      properties,
      geometry: { type: 'Point', coordinates: [point.lon, point.lat] },
    }
  })
  return { type: 'FeatureCollection', features }
}

/**
 * Heat weight (0 to 1) at a possibly fractional hour, blended between the two nearest hours.
 * The weight is not simply level / 4: even a Moderate checkpoint should stand out on the map.
 */
export function heatWeight(hour: number, lastHour: number): ExpressionSpecification {
  const clamped = Math.min(Math.max(hour, 0), lastHour)
  const lower = Math.floor(clamped)
  const upper = Math.min(lower + 1, lastHour)
  const blend = clamped - lower

  const level: ExpressionSpecification = [
    '+',
    ['*', 1 - blend, ['to-number', ['get', `h${lower}`], 0]],
    ['*', blend, ['to-number', ['get', `h${upper}`], 0]],
  ]
  return ['interpolate', ['linear'], level, 0, 0, 1, 0.4, 4, 1]
}

/** Paint expression that colours a feature by its `level` property. */
export function levelColor(): ExpressionSpecification {
  return [
    'match',
    ['get', 'level'],
    0,
    RISK_COLORS[0],
    1,
    RISK_COLORS[1],
    2,
    RISK_COLORS[2],
    3,
    RISK_COLORS[3],
    4,
    RISK_COLORS[4],
    '#868e96',
  ]
}

export function routeBounds(routes: Route[]): LngLatBounds | null {
  let minLon = Infinity
  let minLat = Infinity
  let maxLon = -Infinity
  let maxLat = -Infinity

  for (const route of routes) {
    for (const segment of route.segments) {
      for (const [lon, lat] of segment.coordinates) {
        minLon = Math.min(minLon, lon)
        maxLon = Math.max(maxLon, lon)
        minLat = Math.min(minLat, lat)
        maxLat = Math.max(maxLat, lat)
      }
    }
  }
  return Number.isFinite(minLon) ? [[minLon, minLat], [maxLon, maxLat]] : null
}
