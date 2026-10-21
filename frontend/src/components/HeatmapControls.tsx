import { useEffect, useRef, useState } from 'react'
import { formatDateTime, formatHourOffset, timeZoneAbbreviation } from '../lib/format'
import styles from './HeatmapControls.module.css'

const HOURS_PER_SECOND = 4

interface Props {
  visible: boolean
  onVisibleChange: (visible: boolean) => void
  hour: number
  onHourChange: (hour: number) => void
  maxHour: number
  startIso: string
  timeZone: string
}

export function HeatmapControls({ visible, onVisibleChange, hour, onHourChange, maxHour, startIso, timeZone }: Props) {
  const [playing, setPlaying] = useState(false)

  // the animation loop reads these through refs so it never restarts while it runs
  const hourRef = useRef(hour)
  const changeRef = useRef(onHourChange)
  useEffect(() => {
    hourRef.current = hour
    changeRef.current = onHourChange
  })

  useEffect(() => {
    if (!playing) return

    let frame = 0
    let last = performance.now()
    const step = (now: number) => {
      const next = hourRef.current + ((now - last) / 1000) * HOURS_PER_SECOND
      last = now
      if (next >= maxHour) {
        changeRef.current(maxHour)
        setPlaying(false)
        return
      }
      changeRef.current(next)
      frame = requestAnimationFrame(step)
    }
    frame = requestAnimationFrame(step)
    return () => cancelAnimationFrame(frame)
  }, [playing, maxHour])

  function togglePlay() {
    if (!playing && hour >= maxHour) onHourChange(0)
    setPlaying(!playing)
  }

  const moment = new Date(new Date(startIso).getTime() + hour * 3_600_000).toISOString()

  return (
    <section className={styles.panel} aria-label="Weather heatmap">
      <div className={styles.top}>
        <label className={styles.toggle}>
          <input type="checkbox" checked={visible} onChange={(event) => onVisibleChange(event.target.checked)} />
          Weather heatmap
        </label>
        {visible && (
          <p className={styles.time} aria-live="off">
            <strong>
              {formatDateTime(moment, timeZone)} {timeZoneAbbreviation(moment, timeZone)}
            </strong>
            <span>{hour < 0.01 ? 'At departure' : `${formatHourOffset(hour)} after departure`}</span>
          </p>
        )}
      </div>

      {visible && (
        <div className={styles.slider}>
          <button
            type="button"
            className={styles.play}
            onClick={togglePlay}
            aria-label={playing ? 'Pause forecast animation' : 'Play forecast animation'}
          >
            {playing ? '❚❚' : '▶'}
          </button>
          <div className={styles.track}>
            <input
              type="range"
              min={0}
              max={maxHour}
              step={0.25}
              value={hour}
              onChange={(event) => {
                setPlaying(false)
                onHourChange(Number(event.target.value))
              }}
              aria-label="Hours after departure"
              aria-valuetext={`${formatHourOffset(hour)} after departure`}
            />
            <div className={styles.ticks} aria-hidden="true">
              {[0, 12, 24, 36, 48]
                .filter((tick) => tick <= maxHour)
                .map((tick) => (
                  <span key={tick}>{tick === 0 ? 'Depart' : `+${tick}h`}</span>
                ))}
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
