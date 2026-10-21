import { useQuery } from '@tanstack/react-query'
import { useDebouncedValue } from '../hooks/useDebouncedValue'
import { request } from './client'
import type { Place } from './types'

export const MIN_SEARCH_LENGTH = 3

async function searchPlaces(text: string, signal: AbortSignal): Promise<Place[]> {
  const data = await request<{ results: Place[] }>(`/geocode/?q=${encodeURIComponent(text)}`, { signal })
  return data.results
}

export function usePlaceSearch(text: string) {
  const query = useDebouncedValue(text.trim(), 300)
  const enabled = query.length >= MIN_SEARCH_LENGTH

  const result = useQuery({
    queryKey: ['places', query.toLowerCase()],
    queryFn: ({ signal }) => searchPlaces(query, signal),
    enabled,
    staleTime: 5 * 60_000,
    retry: false,
  })

  return {
    places: enabled ? (result.data ?? []) : [],
    // true from the moment the text changes until the answer for it arrives
    isSearching: text.trim().length >= MIN_SEARCH_LENGTH && (query !== text.trim() || result.isFetching),
    isError: enabled && result.isError,
    searched: enabled && result.isSuccess && query === text.trim(),
  }
}
