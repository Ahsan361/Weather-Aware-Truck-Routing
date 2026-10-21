import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Place } from '../api/types'
import { PlaceInput } from './PlaceInput'

const DALLAS: Place = { label: 'Dallas, TX, USA', lat: 32.78, lon: -96.8 }
const DALLAS_NC: Place = { label: 'Dallas, NC, USA', lat: 35.35, lon: -81.18 }

function answerWith(places: Place[], status = 200) {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: status === 200,
    status,
    json: async () => (status === 200 ? { results: places } : { detail: 'Address search failed' }),
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

// the real form owns the selected place, so the test does too
function Harness({ onChange }: { onChange: (place: Place | null) => void }) {
  const [value, setValue] = useState<Place | null>(null)
  return (
    <PlaceInput
      label="From"
      marker="A"
      value={value}
      onChange={(place) => {
        setValue(place)
        onChange(place)
      }}
    />
  )
}

function setup(onChange = vi.fn()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <Harness onChange={onChange} />
    </QueryClientProvider>,
  )
  return { onChange, user: userEvent.setup(), input: screen.getByRole('combobox', { name: 'From' }) }
}

afterEach(() => vi.unstubAllGlobals())

describe('PlaceInput', () => {
  it('does not search until there are three characters', async () => {
    const fetchMock = answerWith([DALLAS])
    const { user, input } = setup()
    await user.type(input, 'Da')
    await new Promise((resolve) => setTimeout(resolve, 450))
    expect(fetchMock).not.toHaveBeenCalled()
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  })

  it('shows suggestions for what was typed', async () => {
    const fetchMock = answerWith([DALLAS, DALLAS_NC])
    const { user, input } = setup()
    await user.type(input, 'Dallas')

    expect(await screen.findByRole('option', { name: DALLAS.label })).toBeInTheDocument()
    expect(screen.getAllByRole('option')).toHaveLength(2)
    expect(String(fetchMock.mock.calls[0][0])).toContain('q=Dallas')
  })

  it('waits for a pause in typing instead of searching on every key', async () => {
    const fetchMock = answerWith([DALLAS])
    const { user, input } = setup()
    await user.type(input, 'Dallas')
    await screen.findByRole('option')
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('picks a suggestion with the mouse', async () => {
    answerWith([DALLAS, DALLAS_NC])
    const { user, input, onChange } = setup()
    await user.type(input, 'Dallas')
    await user.click(await screen.findByRole('option', { name: DALLAS_NC.label }))

    expect(onChange).toHaveBeenLastCalledWith(DALLAS_NC)
    expect(input).toHaveValue(DALLAS_NC.label)
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Place selected')).toBeInTheDocument()
  })

  it('picks a suggestion with the keyboard', async () => {
    answerWith([DALLAS, DALLAS_NC])
    const { user, input, onChange } = setup()
    await user.type(input, 'Dallas')
    await screen.findByRole('option', { name: DALLAS.label })

    await user.keyboard('{ArrowDown}{ArrowDown}{ArrowUp}{Enter}')
    expect(onChange).toHaveBeenLastCalledWith(DALLAS)
    expect(input).toHaveValue(DALLAS.label)
  })

  it('closes the list on Escape without choosing anything', async () => {
    answerWith([DALLAS])
    const { user, input, onChange } = setup()
    await user.type(input, 'Dallas')
    await screen.findByRole('option')
    await user.keyboard('{Escape}')

    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
    expect(onChange).not.toHaveBeenCalled()
  })

  it('forgets the chosen place as soon as the text is edited', async () => {
    answerWith([DALLAS])
    const { user, input, onChange } = setup()
    await user.type(input, 'Dallas')
    await user.click(await screen.findByRole('option'))
    expect(onChange).toHaveBeenLastCalledWith(DALLAS)

    await user.type(input, 'x')
    expect(onChange).toHaveBeenLastCalledWith(null)
    expect(screen.queryByLabelText('Place selected')).not.toBeInTheDocument()
  })

  it('says so when nothing matches', async () => {
    answerWith([])
    const { user, input } = setup()
    await user.type(input, 'zzzzzz')
    expect(await screen.findByText('No places found.')).toBeInTheDocument()
  })

  it('says so when the search service is down', async () => {
    answerWith([], 502)
    const { user, input } = setup()
    await user.type(input, 'Dallas')
    await waitFor(() => expect(screen.getByText(/unavailable/i)).toBeInTheDocument())
  })
})
