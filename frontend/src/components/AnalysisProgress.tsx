import { useEffect, useState } from 'react'
import styles from './AnalysisProgress.module.css'

// what the server is actually doing while the request runs, roughly in order
const STAGES = [
  'Finding route options…',
  'Placing weather checkpoints along each route…',
  'Pulling the hourly forecast for each checkpoint…',
  'Scoring weather risk for your load…',
]
const STAGE_MS = 2200

export function AnalysisProgress() {
  const [stage, setStage] = useState(0)

  useEffect(() => {
    const timer = setInterval(() => setStage((current) => Math.min(current + 1, STAGES.length - 1)), STAGE_MS)
    return () => clearInterval(timer)
  }, [])

  return (
    <div className={styles.progress} role="status" aria-live="polite">
      <span className={styles.spinner} aria-hidden="true" />
      <div>
        <p className={styles.stage}>{STAGES[stage]}</p>
        <p className={styles.hint}>Long trips can take up to 10 seconds.</p>
      </div>
    </div>
  )
}
