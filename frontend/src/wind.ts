import i18n from './i18n'
import type { Alignment, RainTier, Segment } from './types'

/**
 * Colours for the three wind alignments.
 *
 * The route is coloured by direction rather than by score, because direction
 * is the part the forecast actually predicts well.
 */
export const ALIGNMENT_KEY = {
  headwind: 'wind.headwind',
  crosswind: 'wind.crosswind',
  tailwind: 'wind.tailwind',
} as const

export const RAIN_KEY = {
  light: 'rain.light',
  moderate: 'rain.moderate',
  heavy: 'rain.heavy',
} as const

export const ALIGNMENT_COLOUR: Record<Alignment, string> = {
  headwind: '#dc2626',
  crosswind: '#d97706',
  tailwind: '#16a34a',
}

/**
 * Rain gets its own visual channel, since colour along the route is already
 * spent on wind direction. It is drawn as a wider casing underneath the line,
 * deepening in blue as the rate rises.
 */
export const RAIN_COLOUR: Record<RainTier, string> = {
  light: '#7dd3fc',
  moderate: '#38bdf8',
  heavy: '#2563eb',
}

export const RAIN_WIDTH: Record<RainTier, number> = {
  light: 12,
  moderate: 15,
  heavy: 18,
}

/** Wind below this is not worth calling a head-, tail- or crosswind. */
const NOTABLE_WIND_KM_H = 12

/** Whether a segment's wind is strong enough to be worth showing as a direction. */
export function isNotable(segment: Segment): boolean {
  if (segment.tailwind_km_h === null || segment.crosswind_km_h === null) return false
  return (
    Math.abs(segment.tailwind_km_h) >= NOTABLE_WIND_KM_H ||
    segment.crosswind_km_h >= NOTABLE_WIND_KM_H
  )
}

/** Colour for a segment's polyline, muted when the wind is unremarkable. */
export function segmentColour(segment: Segment): string {
  if (!isNotable(segment) || !segment.alignment) return '#94a3b8'
  return ALIGNMENT_COLOUR[segment.alignment]
}

/** Direction the wind blows towards, which is what an arrow should point at. */
export function arrowRotation(windDirectionDeg: number): number {
  return (windDirectionDeg + 180) % 360
}

/** Format a timestamp as a local time of day. */
export function formatTime(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleTimeString(i18n.resolvedLanguage, {
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** Format a distance in kilometres with sensible precision. */
export function formatKm(km: number): string {
  return km >= 10 ? km.toFixed(0) : km.toFixed(1)
}
