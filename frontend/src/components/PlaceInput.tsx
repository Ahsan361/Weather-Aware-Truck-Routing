import { useId, useState } from 'react'
import type { KeyboardEvent } from 'react'
import { MIN_SEARCH_LENGTH, usePlaceSearch } from '../api/geocode'
import type { Place } from '../api/types'
import styles from './PlaceInput.module.css'

interface Props {
  label: string
  marker: string
  value: Place | null
  onChange: (place: Place | null) => void
  placeholder?: string
  error?: string
}

export function PlaceInput({ label, marker, value, onChange, placeholder, error }: Props) {
  const id = useId()
  const listId = `${id}-list`
  const [text, setText] = useState(value?.label ?? '')
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)

  // follow the parent when it swaps the place for another one (typing clears it, so skip null)
  const [seen, setSeen] = useState(value)
  if (value !== seen) {
    setSeen(value)
    if (value) setText(value.label)
  }

  // once a place is picked there is nothing left to search for
  const { places, isSearching, isError, searched } = usePlaceSearch(value ? '' : text)
  const showList = open && !value && text.trim().length >= MIN_SEARCH_LENGTH

  function choose(place: Place) {
    setText(place.label)
    setOpen(false)
    setActive(-1)
    onChange(place)
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setOpen(true)
      setActive((current) => Math.min(current + 1, places.length - 1))
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActive((current) => Math.max(current - 1, 0))
    } else if (event.key === 'Enter' && showList && places[active]) {
      event.preventDefault()
      choose(places[active])
    } else if (event.key === 'Escape') {
      setOpen(false)
    }
  }

  return (
    <div className={styles.field}>
      <label className={styles.label} htmlFor={id}>
        {label}
      </label>
      <div className={styles.control}>
        <span className={styles.marker} aria-hidden="true">
          {marker}
        </span>
        <input
          id={id}
          className={styles.input}
          value={text}
          placeholder={placeholder}
          autoComplete="off"
          role="combobox"
          aria-expanded={showList}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={showList && active >= 0 ? `${id}-option-${active}` : undefined}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? `${id}-error` : undefined}
          onChange={(event) => {
            setText(event.target.value)
            setActive(-1)
            setOpen(true)
            if (value) onChange(null)
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setOpen(false)}
          onKeyDown={handleKeyDown}
        />
        {value && (
          <span className={styles.check} aria-label="Place selected" title="Place selected">
            ✓
          </span>
        )}

        {showList && (
          <ul id={listId} className={styles.list} role="listbox" aria-label={`${label} suggestions`}>
            {places.map((place, index) => (
              <li
                key={`${place.lat},${place.lon}`}
                id={`${id}-option-${index}`}
                role="option"
                aria-selected={index === active}
                className={index === active ? `${styles.option} ${styles.active}` : styles.option}
                // keep focus in the input so the click isn't swallowed by a blur
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => choose(place)}
                onMouseEnter={() => setActive(index)}
              >
                {place.label}
              </li>
            ))}
            {places.length === 0 && (
              <li className={styles.status} role="presentation">
                {isError
                  ? 'Address search is unavailable right now.'
                  : isSearching
                    ? 'Searching…'
                    : searched
                      ? 'No places found.'
                      : 'Searching…'}
              </li>
            )}
          </ul>
        )}
      </div>
      {error && (
        <p id={`${id}-error`} className={styles.error}>
          {error}
        </p>
      )}
    </div>
  )
}
