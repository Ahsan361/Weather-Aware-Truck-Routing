const BASE_URL = `${import.meta.env.VITE_API_URL ?? ''}/api`

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/** Turns the shapes the backend answers with into one sentence a person can read. */
export function describeErrors(body: unknown): string | null {
  if (!body || typeof body !== 'object') return null

  const detail = (body as { detail?: unknown }).detail
  if (typeof detail === 'string') return detail

  const parts: string[] = []
  for (const [field, problem] of Object.entries(body)) {
    const text = flatten(problem)
    if (text) parts.push(`${humanize(field)}: ${text}`)
  }
  return parts.length ? parts.join(' ') : null
}

function flatten(problem: unknown): string {
  if (typeof problem === 'string') return problem
  if (Array.isArray(problem)) return problem.map(flatten).filter(Boolean).join(' ')
  if (problem && typeof problem === 'object') {
    return Object.values(problem).map(flatten).filter(Boolean).join(' ')
  }
  return ''
}

function humanize(field: string): string {
  const spaced = field.replace(/_/g, ' ')
  return spaced.charAt(0).toUpperCase() + spaced.slice(1)
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init.headers },
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError('Could not reach the server. Check your connection and try again.', 0)
  }

  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new ApiError(describeErrors(body) ?? `The server answered ${response.status}.`, response.status)
  }
  return response.json() as Promise<T>
}
