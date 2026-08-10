import type { AnalyseRequest, Analysis } from './types'

/** Send a GPX file to the backend and return the forecast along the route. */
export async function analyseRoute({
  gpx,
  avgSpeedKmh,
  startTime,
}: AnalyseRequest): Promise<Analysis> {
  const body = new FormData()
  body.append('gpx', gpx)
  if (avgSpeedKmh !== undefined) body.append('avg_speed_kmh', String(avgSpeedKmh))
  if (startTime !== undefined) body.append('start_time', startTime)

  const response = await fetch('/api/analyze', { method: 'POST', body })

  if (!response.ok) {
    throw new Error(await readError(response))
  }
  return response.json()
}

/** Pull a readable message out of a failed response. */
async function readError(response: Response): Promise<string> {
  try {
    const payload = await response.json()
    if (typeof payload?.detail === 'string') return payload.detail
  } catch {
    // Fall through to the status text below.
  }
  return `Die Auswertung ist fehlgeschlagen (${response.status}).`
}
