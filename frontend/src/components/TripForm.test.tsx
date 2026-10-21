import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Place } from '../api/types'
import { TripForm } from './TripForm'

const CHICAGO: Place = { label: 'Chicago, IL, USA', lat: 41.88, lon: -87.63 }
const DENVER: Place = { label: 'Denver, CO, USA', lat: 39.74, lon: -104.99 }

// the search answers from a small fixed directory
function stubSearch() {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      const query = decodeURIComponent(url.split('q=')[1]).toLowerCase()
      const results = [CHICAGO, DENVER].filter((place) => place.label.toLowerCase().startsWith(query))
      return { ok: true, status: 200, json: async () => ({ results }) }
    }),
  )
}

function setup(pending = false) {
  stubSearch()
  const onSubmit = vi.fn()
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <TripForm pending={pending} onSubmit={onSubmit} />
    </QueryClientProvider>,
  )
  return { onSubmit, user: userEvent.setup() }
}

async function pickPlace(user: ReturnType<typeof userEvent.setup>, label: string, text: string, option: string) {
  await user.type(screen.getByRole('combobox', { name: label }), text)
  await user.click(await screen.findByRole('option', { name: option }))
}

afterEach(() => vi.unstubAllGlobals())

describe('TripForm', () => {
  it('will not submit without places and says what is missing', async () => {
    const { onSubmit, user } = setup()
    await user.click(screen.getByRole('button', { name: /find the safest route/i }))

    expect(onSubmit).not.toHaveBeenCalled()
    expect(screen.getByText(/pick a starting point/i)).toBeInTheDocument()
    expect(screen.getByText(/pick a destination/i)).toBeInTheDocument()
  })

  it('rejects a load outside the allowed range', async () => {
    const { onSubmit, user } = setup()
    const load = screen.getByLabelText('Load weight')
    await user.clear(load)
    await user.type(load, '250000')
    await user.click(screen.getByRole('button', { name: /find the safest route/i }))

    expect(onSubmit).not.toHaveBeenCalled()
    expect(screen.getByText(/between 0 and 100,000 lb/i)).toBeInTheDocument()
  })

  it('submits the trip with everything the api needs', async () => {
    const { onSubmit, user } = setup()
    await pickPlace(user, 'From', 'Chicago', CHICAGO.label)
    await pickPlace(user, 'To', 'Denver', DENVER.label)

    await user.click(screen.getByRole('button', { name: /Heavy/ }))
    await user.click(screen.getByRole('radio', { name: '50 mi' }))
    await user.click(screen.getByRole('button', { name: /find the safest route/i }))

    expect(onSubmit).toHaveBeenCalledTimes(1)
    expect(onSubmit).toHaveBeenCalledWith({
      origin: CHICAGO,
      destination: DENVER,
      departure: expect.stringMatching(/^\d{4}-\d{2}-\d{2}T06:00$/),
      load_lb: 45_000,
      interval_miles: 50,
    })
  })

  it('the presets fill in the load', async () => {
    const { user } = setup()
    await user.click(screen.getByRole('button', { name: /Light/ }))
    expect(screen.getByLabelText('Load weight')).toHaveValue(20_000)
  })

  it('swaps the start and the destination', async () => {
    const { onSubmit, user } = setup()
    await pickPlace(user, 'From', 'Chicago', CHICAGO.label)
    await pickPlace(user, 'To', 'Denver', DENVER.label)
    await user.click(screen.getByRole('button', { name: /swap/i }))

    expect(screen.getByRole('combobox', { name: 'From' })).toHaveValue(DENVER.label)
    expect(screen.getByRole('combobox', { name: 'To' })).toHaveValue(CHICAGO.label)

    await user.click(screen.getByRole('button', { name: /find the safest route/i }))
    expect(onSubmit.mock.calls[0][0]).toMatchObject({ origin: DENVER, destination: CHICAGO })
  })

  it('refuses a trip from a place to itself', async () => {
    const { onSubmit, user } = setup()
    await pickPlace(user, 'From', 'Chicago', CHICAGO.label)
    await pickPlace(user, 'To', 'Chicago', CHICAGO.label)
    await user.click(screen.getByRole('button', { name: /find the safest route/i }))

    expect(onSubmit).not.toHaveBeenCalled()
    expect(screen.getByText(/same as the starting point/i)).toBeInTheDocument()
  })

  it('is disabled and says so while a request is running', () => {
    setup(true)
    const button = screen.getByRole('button', { name: /analyzing routes/i })
    expect(button).toBeDisabled()
  })
})
