import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, describeErrors, request } from './client'

describe('describeErrors', () => {
  it('uses the detail message when there is one', () => {
    expect(describeErrors({ detail: 'Couldn\'t plan routes: service down' })).toBe("Couldn't plan routes: service down")
  })

  it('turns field errors into a sentence', () => {
    expect(describeErrors({ load_lb: ['Ensure this value is less than or equal to 100000.'] })).toBe(
      'Load lb: Ensure this value is less than or equal to 100000.',
    )
  })

  it('digs into nested field errors', () => {
    expect(describeErrors({ origin: { lat: ['Ensure this value is less than or equal to 90.'] } })).toBe(
      'Origin: Ensure this value is less than or equal to 90.',
    )
  })

  it('joins several problems', () => {
    expect(describeErrors({ departure: ["Departure can't be in the past."], load_lb: ['Bad.'] })).toBe(
      "Departure: Departure can't be in the past. Load lb: Bad.",
    )
  })

  it.each([null, undefined, 'text', 42, {}])('returns null for %s', (body) => {
    expect(describeErrors(body)).toBeNull()
  })
})

describe('request', () => {
  afterEach(() => vi.unstubAllGlobals())

  function stubFetch(response: Partial<Response> & { json?: () => Promise<unknown> }) {
    const fetchMock = vi.fn().mockResolvedValue(response)
    vi.stubGlobal('fetch', fetchMock)
    return fetchMock
  }

  it('returns the parsed body and calls the api prefix', async () => {
    const fetchMock = stubFetch({ ok: true, json: async () => ({ hello: 'world' }) })
    await expect(request('/health/')).resolves.toEqual({ hello: 'world' })
    expect(fetchMock.mock.calls[0][0]).toBe('/api/health/')
  })

  it('turns an error response into an ApiError with the server message', async () => {
    stubFetch({ ok: false, status: 503, json: async () => ({ detail: 'The weather service is busy.' }) })
    await expect(request('/x')).rejects.toMatchObject({
      name: 'ApiError',
      status: 503,
      message: 'The weather service is busy.',
    })
  })

  it('still gives a message when the error body is not JSON', async () => {
    stubFetch({
      ok: false,
      status: 500,
      json: async () => {
        throw new SyntaxError('bad json')
      },
    })
    await expect(request('/x')).rejects.toThrow('The server answered 500.')
  })

  it('explains a network failure plainly', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    const error = await request('/x').catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(0)
    expect((error as ApiError).message).toMatch(/could not reach the server/i)
  })

  it('lets an abort through untouched, so callers can ignore it', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new DOMException('Aborted', 'AbortError')))
    await expect(request('/x')).rejects.toMatchObject({ name: 'AbortError' })
  })
})
