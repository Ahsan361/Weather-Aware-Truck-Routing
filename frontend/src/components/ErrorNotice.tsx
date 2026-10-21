import styles from './ErrorNotice.module.css'

interface Props {
  message: string
  onRetry: () => void
}

export function ErrorNotice({ message, onRetry }: Props) {
  return (
    <div className={styles.notice} role="alert">
      <p>{message}</p>
      <button type="button" onClick={onRetry}>
        Try again
      </button>
    </div>
  )
}
