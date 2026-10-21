import { useState } from 'react'
import type { FormEvent } from 'react'
import type { AnalyzeRequest, IntervalMiles, Place } from '../api/types'
import { defaultDeparture, toInputValue } from '../lib/format'
import { PlaceInput } from './PlaceInput'
import styles from './TripForm.module.css'

const MAX_LOAD_LB = 100_000
const INTERVALS: IntervalMiles[] = [10, 25, 50]
// the load rules in the brief switch on at 30,000 and 40,000 lb, so these show them off
const LOAD_PRESETS = [
  { label: 'Light', lb: 20_000 },
  { label: 'Medium', lb: 35_000 },
  { label: 'Heavy', lb: 45_000 },
  { label: 'Max', lb: 80_000 },
]

interface Props {
  pending: boolean
  onSubmit: (request: AnalyzeRequest) => void
}

type Errors = Partial<Record<'origin' | 'destination' | 'departure' | 'load', string>>

export function TripForm({ pending, onSubmit }: Props) {
  const [origin, setOrigin] = useState<Place | null>(null)
  const [destination, setDestination] = useState<Place | null>(null)
  const [departure, setDeparture] = useState(() => defaultDeparture())
  const [earliestDeparture] = useState(() => toInputValue(new Date()))
  const [load, setLoad] = useState('45000')
  const [interval, setInterval] = useState<IntervalMiles>(25)
  const [errors, setErrors] = useState<Errors>({})

  function validate(): Errors {
    const found: Errors = {}
    if (!origin) found.origin = 'Pick a starting point from the suggestions.'
    if (!destination) found.destination = 'Pick a destination from the suggestions.'
    if (origin && destination && origin.lat === destination.lat && origin.lon === destination.lon) {
      found.destination = 'The destination is the same as the starting point.'
    }
    if (!departure) found.departure = 'Choose when the truck leaves.'
    const pounds = Number(load)
    if (load.trim() === '' || !Number.isFinite(pounds) || pounds < 0 || pounds > MAX_LOAD_LB) {
      found.load = `Enter a weight between 0 and ${MAX_LOAD_LB.toLocaleString('en-US')} lb.`
    }
    return found
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const found = validate()
    setErrors(found)
    if (Object.keys(found).length > 0 || !origin || !destination) return

    onSubmit({
      origin,
      destination,
      departure,
      load_lb: Number(load),
      interval_miles: interval,
    })
  }

  function swapPlaces() {
    setOrigin(destination)
    setDestination(origin)
  }

  return (
    <form className={styles.form} onSubmit={handleSubmit} noValidate>
      <div className={styles.places}>
        <PlaceInput
          label="From"
          marker="A"
          value={origin}
          onChange={setOrigin}
          placeholder="City or address"
          error={errors.origin}
        />
        <button
          type="button"
          className={styles.swap}
          onClick={swapPlaces}
          aria-label="Swap start and destination"
          title="Swap start and destination"
        >
          ⇅
        </button>
        <PlaceInput
          label="To"
          marker="B"
          value={destination}
          onChange={setDestination}
          placeholder="City or address"
          error={errors.destination}
        />
      </div>

      <div className={styles.row}>
        <div className={styles.field}>
          <label htmlFor="departure">Departure</label>
          <input
            id="departure"
            type="datetime-local"
            value={departure}
            min={earliestDeparture}
            onChange={(event) => setDeparture(event.target.value)}
            aria-invalid={errors.departure ? true : undefined}
          />
          <p className={styles.hint}>Local time at the starting point</p>
          {errors.departure && <p className={styles.error}>{errors.departure}</p>}
        </div>

        <div className={styles.field}>
          <label htmlFor="load">Load weight</label>
          <div className={styles.suffixed}>
            <input
              id="load"
              type="number"
              inputMode="numeric"
              min={0}
              max={MAX_LOAD_LB}
              step={500}
              value={load}
              onChange={(event) => setLoad(event.target.value)}
              aria-invalid={errors.load ? true : undefined}
            />
            <span aria-hidden="true">lb</span>
          </div>
          {errors.load && <p className={styles.error}>{errors.load}</p>}
        </div>
      </div>

      <div className={styles.presets} role="group" aria-label="Load presets">
        {LOAD_PRESETS.map((preset) => (
          <button
            key={preset.label}
            type="button"
            className={Number(load) === preset.lb ? `${styles.preset} ${styles.selected}` : styles.preset}
            onClick={() => setLoad(String(preset.lb))}
          >
            {preset.label} <span>{preset.lb.toLocaleString('en-US')}</span>
          </button>
        ))}
      </div>

      <fieldset className={styles.interval}>
        <legend>Check the weather every</legend>
        <div className={styles.segments}>
          {INTERVALS.map((miles) => (
            <label key={miles} className={interval === miles ? `${styles.segment} ${styles.selected}` : styles.segment}>
              <input
                type="radio"
                name="interval"
                value={miles}
                checked={interval === miles}
                onChange={() => setInterval(miles)}
              />
              {miles} mi
            </label>
          ))}
        </div>
        <p className={styles.hint}>Closer checkpoints catch more weather but take a little longer.</p>
      </fieldset>

      <button type="submit" className={styles.submit} disabled={pending}>
        {pending ? 'Analyzing routes…' : 'Find the safest route'}
      </button>
    </form>
  )
}
