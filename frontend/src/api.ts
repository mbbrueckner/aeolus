import i18n from './i18n'
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

/**
 * Turn a failed response into a message in the reader's language.
 *
 * The server sends a stable code alongside an English fallback, so the wording
 * lives in the translations rather than in the API.
 */
async function readError(response: Response): Promise<string> {
  try {
    const detail = (await response.json())?.detail
    const code = typeof detail === 'object' ? detail?.code : undefined

    if (typeof code === 'string' && i18n.exists(`errors.${code}`)) {
      return i18n.t(`errors.${code}` as 'errors.unknown')
    }
    if (typeof detail === 'string') return detail
    if (typeof detail?.message === 'string') return detail.message
  } catch {
    // Fall through to the status-based message below.
  }
  return i18n.t('errors.unknown', { status: response.status })
}
