import { describe, expect, it } from 'vitest'
import {
  defaultDeparture,
  formatDateTime,
  formatDuration,
  formatHourOffset,
  formatMiles,
  formatTime,
  timeZoneAbbreviation,
  toInputValue,
} from './format'

describe('formatDuration', () => {
  it.each([
    [0, '0m'],
    [45, '45m'],
    [60, '1h'],
    [125, '2h 5m'],
    [1068, '17h 48m'],
    [59.6, '1h'],
  ])('%s minutes -> %s', (minutes, expected) => {
    expect(formatDuration(minutes)).toBe(expected)
  })
})

describe('formatMiles', () => {
  it('rounds and adds thousands separators', () => {
    expect(formatMiles(1004.6)).toBe('1,005 mi')
    expect(formatMiles(32.2)).toBe('32 mi')
  })
})

describe('time formatting', () => {
  // 18:30 UTC is 1:30 PM in Chicago (CDT) and 11:30 AM in Los Angeles (PDT) on this date
  const iso = '2026-10-20T18:30:00Z'

  it('formats in the requested time zone', () => {
    expect(formatTime(iso, 'America/Chicago')).toBe('1:30 PM')
    expect(formatTime(iso, 'America/Los_Angeles')).toBe('11:30 AM')
  })

  it('includes the weekday and date in the long form', () => {
    expect(formatDateTime(iso, 'America/Chicago')).toBe('Tue, Oct 20, 1:30 PM')
  })

  it('crosses midnight correctly', () => {
    expect(formatDateTime('2026-10-21T03:30:00Z', 'America/Los_Angeles')).toBe('Tue, Oct 20, 8:30 PM')
  })

  it('names the zone at that moment', () => {
    expect(timeZoneAbbreviation(iso, 'America/Chicago')).toBe('CDT')
    expect(timeZoneAbbreviation('2026-12-20T18:30:00Z', 'America/Chicago')).toBe('CST')
  })

  it('falls back to UTC for a zone the browser does not know', () => {
    expect(formatTime(iso, 'Not/AZone')).toBe('6:30 PM')
    expect(timeZoneAbbreviation(iso, 'Not/AZone')).toBe('UTC')
  })
})

describe('formatHourOffset', () => {
  it.each([
    [0, '+0h'],
    [0.25, '+15m'],
    [1, '+1h'],
    [13.25, '+13h 15m'],
    [48, '+48h'],
  ])('%s hours -> %s', (hours, expected) => {
    expect(formatHourOffset(hours)).toBe(expected)
  })
})

describe('departure helpers', () => {
  it('toInputValue pads every part', () => {
    expect(toInputValue(new Date(2026, 0, 5, 7, 4))).toBe('2026-01-05T07:04')
  })

  it('defaults to tomorrow at 06:00', () => {
    expect(defaultDeparture(new Date(2026, 10, 3, 15, 42))).toBe('2026-11-04T06:00')
  })

  it('rolls over month ends', () => {
    expect(defaultDeparture(new Date(2026, 9, 31, 23, 59))).toBe('2026-11-01T06:00')
  })
})
