import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { route } from '../test/fixtures'
import { RouteCard } from './RouteCard'

function setup(overrides = {}, props = {}) {
  const onSelect = vi.fn()
  render(
    <RouteCard
      route={route(0, overrides)}
      routeCount={3}
      timeZone="America/Chicago"
      selected={false}
      onSelect={onSelect}
      {...props}
    />,
  )
  return { onSelect }
}

describe('RouteCard', () => {
  it('shows the headline numbers for the route', () => {
    setup({ duration_minutes: 1068, distance_miles: 1004.6 })
    expect(screen.getByText('Route 1')).toBeInTheDocument()
    expect(screen.getByText('17h 48m')).toBeInTheDocument()
    expect(screen.getByText('1,005 mi')).toBeInTheDocument()
    expect(screen.getByText(/Arrives Tue, Nov 3, 8:00 AM/)).toBeInTheDocument()
  })

  it('marks the recommended route and ranks the others', () => {
    setup()
    expect(screen.getByText('Recommended')).toBeInTheDocument()

    setup({ id: 2, recommended: false, rank: 3 })
    expect(screen.getByText('#3 of 3')).toBeInTheDocument()
  })

  it('describes the weather mix for screen readers', () => {
    setup({
      summary: { miles_by_level: [60, 20, 15, 5, 0], avg_risk: 0.7, worst_level: 3 },
    })
    expect(screen.getByRole('img')).toHaveAccessibleName(
      'Weather along the route: 60 miles Low, 20 miles Moderate, 15 miles High, 5 miles Severe, 0 miles No Travel',
    )
  })

  it('lists the miles spent in each risky level, worst first, and skips Low', () => {
    setup({
      summary: { miles_by_level: [60, 20, 15, 5, 0], avg_risk: 0.7, worst_level: 3 },
    })
    expect(screen.getByText('Severe 5 mi · High 15 mi · Moderate 20 mi')).toBeInTheDocument()
  })

  it('has no exposure line for a clear route', () => {
    setup()
    expect(screen.queryByText(/mi ·/)).not.toBeInTheDocument()
    expect(screen.getByText('Worst: Low')).toBeInTheDocument()
    expect(screen.getByText(/Avg risk 0\.00/)).toBeInTheDocument()
  })

  it('reports the worst level and average risk', () => {
    setup({ summary: { miles_by_level: [90, 0, 0, 0, 10], avg_risk: 0.4, worst_level: 4 } })
    expect(screen.getByText('Worst: No Travel')).toBeInTheDocument()
    expect(screen.getByText('Avg risk 0.40 / 4')).toBeInTheDocument()
  })

  it('selects when clicked and reflects the selected state', async () => {
    const { onSelect } = setup({}, { selected: true })
    const button = screen.getByRole('button')
    expect(button).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(button)
    expect(onSelect).toHaveBeenCalledTimes(1)
  })
})
