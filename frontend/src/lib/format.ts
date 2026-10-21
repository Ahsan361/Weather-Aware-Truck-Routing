export function formatDuration(minutes: number): string {
  const total = Math.round(minutes)
  const hours = Math.floor(total / 60)
  const mins = total % 60
  if (hours === 0) return `${mins}m`
  return mins === 0 ? `${hours}h` : `${hours}h ${mins}m`
}

export function formatMiles(miles: number): string {
  return `${Math.round(miles).toLocaleString('en-US')} mi`
}

const formatters = new Map<string, Intl.DateTimeFormat>()

function formatterFor(timeZone: string, style: 'full' | 'time'): Intl.DateTimeFormat {
  const key = `${style}|${timeZone}`
  let formatter = formatters.get(key)
  if (!formatter) {
    const options: Intl.DateTimeFormatOptions =
      style === 'full'
        ? { weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }
        : { hour: 'numeric', minute: '2-digit' }
    try {
      formatter = new Intl.DateTimeFormat('en-US', { ...options, timeZone })
    } catch {
      formatter = new Intl.DateTimeFormat('en-US', { ...options, timeZone: 'UTC' })
    }
    formatters.set(key, formatter)
  }
  return formatter
}

/** "Tue, Oct 20, 6:00 AM" in the given time zone. */
export function formatDateTime(iso: string, timeZone: string): string {
  return formatterFor(timeZone, 'full').format(new Date(iso))
}

/** "6:00 AM" in the given time zone. */
export function formatTime(iso: string, timeZone: string): string {
  return formatterFor(timeZone, 'time').format(new Date(iso))
}

/** "CDT", "PST" and so on, for the moment given. */
export function timeZoneAbbreviation(iso: string, timeZone: string): string {
  try {
    const parts = new Intl.DateTimeFormat('en-US', { timeZone, timeZoneName: 'short' }).formatToParts(new Date(iso))
    return parts.find((part) => part.type === 'timeZoneName')?.value ?? timeZone
  } catch {
    return 'UTC'
  }
}

/** 13.25 becomes "+13h 15m". */
export function formatHourOffset(hours: number): string {
  const minutes = Math.round(hours * 60)
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  if (h === 0 && m === 0) return '+0h'
  if (h === 0) return `+${m}m`
  return m === 0 ? `+${h}h` : `+${h}h ${m}m`
}

const pad = (n: number) => String(n).padStart(2, '0')

/** Value for a datetime-local input, in the browser's own time zone. */
export function toInputValue(date: Date): string {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

/** Tomorrow at 06:00, a sensible default for a trip that is planned ahead. */
export function defaultDeparture(now: Date = new Date()): string {
  const tomorrow = new Date(now)
  tomorrow.setDate(tomorrow.getDate() + 1)
  tomorrow.setHours(6, 0, 0, 0)
  return toInputValue(tomorrow)
}
