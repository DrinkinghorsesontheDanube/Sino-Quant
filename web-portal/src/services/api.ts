import type { RunListItem, RunSummary, TradesPayload } from '@/types'

const BASE = '/api/a-share'

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url)
  if (!response.ok) {
    const detail = await response.text().catch(() => '')
    throw new Error(`GET ${url} -> ${response.status} ${detail.slice(0, 200)}`)
  }
  return (await response.json()) as T
}

export function fetchReports() {
  return getJson<{ runs: RunListItem[] }>(`${BASE}/reports`)
}

export function fetchSummary(runId: string) {
  return getJson<RunSummary>(`${BASE}/runs/${encodeURIComponent(runId)}/summary`)
}

export function fetchTrades(runId: string) {
  return getJson<TradesPayload>(`${BASE}/runs/${encodeURIComponent(runId)}/trades`)
}
