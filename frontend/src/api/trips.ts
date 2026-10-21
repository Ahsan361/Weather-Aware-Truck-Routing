import { useMutation } from '@tanstack/react-query'
import { request } from './client'
import type { AnalyzeRequest, AnalyzeResponse } from './types'

function analyzeTrip(body: AnalyzeRequest): Promise<AnalyzeResponse> {
  return request<AnalyzeResponse>('/trips/analyze/', {
    method: 'POST',
    body: JSON.stringify({
      ...body,
      // the API only needs coordinates and a label, not anything else the place object carries
      origin: pick(body.origin),
      destination: pick(body.destination),
    }),
  })
}

function pick({ lat, lon, label }: AnalyzeRequest['origin']) {
  return { lat, lon, label }
}

export function useAnalyzeTrip() {
  return useMutation({ mutationFn: analyzeTrip })
}
