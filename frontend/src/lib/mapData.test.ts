import { describe, expect, it } from 'vitest'
import { checkpoint, route } from '../test/fixtures'
import { checkpointPoints, heatmapPoints, heatWeight, levelColor, routeBounds, routeLines } from './mapData'

describe('routeLines', () => {
  it('makes one line per segment, tagged with its route and risk level', () => {
    const risky = route(1, {
      segments: [
        { level: 0, coordinates: [[0, 0], [1, 1]] },
        { level: 3, coordinates: [[1, 1], [2, 2]] },
      ],
    })
    const { features } = routeLines([route(0), risky])
    expect(features).toHaveLength(3)
    expect(features.map((f) => f.properties)).toEqual([
      { routeId: 0, level: 0 },
      { routeId: 1, level: 0 },
      { routeId: 1, level: 3 },
    ])
    expect(features[2].geometry.coordinates).toEqual([[1, 1], [2, 2]])
  })
})

describe('checkpointPoints', () => {
  it('turns checkpoints into points carrying their index and level', () => {
    const { features } = checkpointPoints(route(0, { checkpoints: [checkpoint(0), checkpoint(25, 2)] }))
    expect(features.map((f) => f.properties)).toEqual([
      { index: 0, level: 0 },
      { index: 1, level: 2 },
    ])
    expect(features[1].geometry.coordinates).toEqual([-99.75, 40.025])
  })

  it('is empty without a route', () => {
    expect(checkpointPoints(undefined).features).toEqual([])
  })
})

describe('heatmapPoints', () => {
  it('stores each hour as its own numeric property', () => {
    const { features } = heatmapPoints({
      start: '2026-11-03T12:00:00Z',
      hours: 2,
      points: [{ lat: 40, lon: -100, levels: [0, 2, 4] }],
    })
    expect(features[0].properties).toEqual({ h0: 0, h1: 2, h2: 4 })
    expect(features[0].geometry.coordinates).toEqual([-100, 40])
  })
})

describe('heatWeight', () => {
  // the expression is ['interpolate', ['linear'], <blended level>, ...stops]
  const blended = (hour: number, last = 48) => (heatWeight(hour, last) as unknown[])[2] as unknown[]

  it('reads the exact hour when the slider is on a whole number', () => {
    const [, weightLower, weightUpper] = blended(5)
    expect(JSON.stringify(weightLower)).toContain('"h5"')
    expect(weightLower).toEqual(['*', 1, ['to-number', ['get', 'h5'], 0]])
    expect(weightUpper).toEqual(['*', 0, ['to-number', ['get', 'h6'], 0]])
  })

  it('blends between two hours in between', () => {
    const [, weightLower, weightUpper] = blended(5.25)
    expect(weightLower).toEqual(['*', 0.75, ['to-number', ['get', 'h5'], 0]])
    expect(weightUpper).toEqual(['*', 0.25, ['to-number', ['get', 'h6'], 0]])
  })

  it('never reads past the last hour or before the first', () => {
    expect(JSON.stringify(blended(48))).not.toContain('h49')
    expect(JSON.stringify(blended(99, 48))).not.toContain('h49')
    expect(JSON.stringify(blended(-3))).toContain('"h0"')
  })

  it('maps a Moderate level to a clearly visible weight', () => {
    const stops = (heatWeight(3, 48) as unknown[]).slice(3)
    expect(stops).toEqual([0, 0, 1, 0.4, 4, 1])
  })
})

describe('levelColor', () => {
  it('has a colour for each of the five levels and a fallback', () => {
    const expression = levelColor() as unknown[]
    expect(expression.slice(0, 2)).toEqual(['match', ['get', 'level']])
    expect(expression).toHaveLength(2 + 5 * 2 + 1)
  })
})

describe('routeBounds', () => {
  it('covers every route', () => {
    const wide = route(2, { segments: [{ level: 0, coordinates: [[-110, 30], [-90, 45]] }] })
    expect(routeBounds([route(0), wide])).toEqual([[-110, 30], [-90, 45]])
  })

  it('is null when there is nothing to bound', () => {
    expect(routeBounds([])).toBeNull()
    expect(routeBounds([route(0, { segments: [] })])).toBeNull()
  })
})
