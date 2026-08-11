import type { Alignment, Field, Segment } from './types'

export interface FieldSample {
  precipitationMmH: number
  windU: number
  windV: number
  gustsMs: number
}

/** Wind speed in km/h from its vector components in m/s. */
export function windSpeedKmH(sample: FieldSample): number {
  return Math.hypot(sample.windU, sample.windV) * 3.6
}

/** Meteorological direction the wind comes from, in degrees. */
export function windDirectionDeg(sample: FieldSample): number {
  const blowingTowards = (Math.atan2(sample.windU, sample.windV) * 180) / Math.PI
  return (blowingTowards + 180 + 360) % 360
}

/** Component of the wind opposing travel along a bearing, in km/h. */
export function headwindKmH(sample: FieldSample, bearingDeg: number): number {
  const bearing = (bearingDeg * Math.PI) / 180
  const along = sample.windU * Math.sin(bearing) + sample.windV * Math.cos(bearing)
  return -along * 3.6
}

export interface WindOnRoute {
  speedKmH: number
  headwindKmH: number
  crosswindKmH: number
  precipitationMmH: number
  alignment: Alignment
}

/** How the wind at a place and time acts on someone travelling a given bearing. */
export function windOnRoute(
  field: Field,
  lat: number,
  lon: number,
  slot: number,
  bearingDeg: number,
): WindOnRoute {
  const sample = sampleField(field, lat, lon, slot)
  const bearing = (bearingDeg * Math.PI) / 180

  const along = sample.windU * Math.sin(bearing) + sample.windV * Math.cos(bearing)
  const across = sample.windU * Math.cos(bearing) - sample.windV * Math.sin(bearing)

  const alignment: Alignment =
    Math.abs(along) < Math.abs(across) ? 'crosswind' : along > 0 ? 'tailwind' : 'headwind'

  return {
    speedKmH: windSpeedKmH(sample),
    headwindKmH: -along * 3.6,
    crosswindKmH: Math.abs(across) * 3.6,
    precipitationMmH: sample.precipitationMmH,
    alignment,
  }
}

export interface LiveSummary {
  totalKm: number
  headwindKm: number
  crosswindKm: number
  tailwindKm: number
  calmKm: number
  rainKm: number
  meanWindKmH: number
  maxRainMmH: number
  maxProbability: number
}

/** Wind below this is not worth calling a head-, tail- or crosswind. */
export const NOTABLE_WIND_KM_H = 12
const NOTABLE_RAIN_MM_H = 0.4

/**
 * Summarise the whole route as it would be at one moment.
 *
 * This treats the route as if the rider were everywhere at once, which is the
 * honest reading when no departure time was given: it answers "what is the
 * weather doing along this route at 15:00", not "what will I meet".
 */
export function summariseAtSlot(
  segments: Segment[],
  field: Field,
  slot: number,
): LiveSummary {
  const totals = {
    totalKm: 0,
    headwindKm: 0,
    crosswindKm: 0,
    tailwindKm: 0,
    calmKm: 0,
    rainKm: 0,
    meanWindKmH: 0,
    maxRainMmH: 0,
    maxProbability: 0,
  }

  for (const segment of segments) {
    const km = segment.distance_km
    const [lat, lon] = segment.point
    const wind = windOnRoute(field, lat, lon, slot, segment.bearing_deg)
    const { precipitationProbability } = sampleProbability(field, lat, lon, slot)

    totals.totalKm += km
    totals.meanWindKmH += wind.speedKmH * km
    totals.maxRainMmH = Math.max(totals.maxRainMmH, wind.precipitationMmH)
    totals.maxProbability = Math.max(totals.maxProbability, precipitationProbability)

    if (wind.precipitationMmH >= NOTABLE_RAIN_MM_H) totals.rainKm += km

    if (Math.max(Math.abs(wind.headwindKmH), wind.crosswindKmH) < NOTABLE_WIND_KM_H) {
      totals.calmKm += km
    } else if (wind.alignment === 'headwind') {
      totals.headwindKm += km
    } else if (wind.alignment === 'tailwind') {
      totals.tailwindKm += km
    } else {
      totals.crosswindKm += km
    }
  }

  totals.meanWindKmH = totals.totalKm > 0 ? totals.meanWindKmH / totals.totalKm : 0
  return totals
}

/** Chance of rain at a place and time, in percent. */
export function sampleProbability(field: Field, lat: number, lon: number, slot: number) {
  const stand: Field = { ...field, precipitation_mm_h: field.precipitation_probability }
  return { precipitationProbability: sampleField(stand, lat, lon, slot).precipitationMmH }
}

/**
 * Position of a moment on the slot axis, clamped to the field's range.
 *
 * The result is fractional: 3.5 means halfway between the fourth and fifth
 * quarter hour.
 */
export function slotIndexAt(field: Field, time: Date): number {
  const last = field.slots.length - 1
  if (last < 1) return 0

  const unix = time.getTime() / 1000
  const step = field.slots[1] - field.slots[0]
  const position = (unix - field.slots[0]) / step

  return Math.min(last, Math.max(0, position))
}

/** The moment a fractional slot position stands for. */
export function timeAtSlot(field: Field, slot: number): Date {
  const last = field.slots.length - 1
  if (last < 0) return new Date()
  if (last < 1) return new Date(field.slots[0] * 1000)

  const step = field.slots[1] - field.slots[0]
  const clamped = Math.min(last, Math.max(0, slot))
  return new Date((field.slots[0] + clamped * step) * 1000)
}

/**
 * Read the field at an arbitrary position by bilinear interpolation.
 *
 * The grid is coarser than the map, so nearest-neighbour sampling would show
 * visible cell edges that suggest detail the forecast does not have.
 */
export function sampleField(
  field: Field,
  lat: number,
  lon: number,
  slot: number,
): FieldSample {
  const { row, column, rowWeight, columnWeight } = locate(field, lat, lon)

  // A fractional slot blends the two quarter hours around it, so scrubbing the
  // clock moves things continuously instead of in fifteen-minute jumps.
  const last = field.slots.length - 1
  const before = Math.max(0, Math.min(last, Math.floor(slot)))
  const after = Math.min(last, before + 1)
  const slotWeight = Math.min(1, Math.max(0, slot - before))

  const read = (grid: number[][][]) => {
    const at = (time: number) => {
      const topLeft = grid[row][column][time]
      const topRight = grid[row][column + 1][time]
      const bottomLeft = grid[row + 1][column][time]
      const bottomRight = grid[row + 1][column + 1][time]

      const top = topLeft + (topRight - topLeft) * columnWeight
      const bottom = bottomLeft + (bottomRight - bottomLeft) * columnWeight
      return top + (bottom - top) * rowWeight
    }

    const early = at(before)
    return slotWeight === 0 ? early : early + (at(after) - early) * slotWeight
  }

  return {
    precipitationMmH: read(field.precipitation_mm_h),
    windU: read(field.wind_u_m_s),
    windV: read(field.wind_v_m_s),
    gustsMs: read(field.wind_gusts_m_s),
  }
}

/** Locate a position within the grid, clamped to its edges. */
function locate(field: Field, lat: number, lon: number) {
  const { latitudes, longitudes } = field
  const row = cell(latitudes, lat)
  const column = cell(longitudes, lon)

  return {
    row: row.index,
    column: column.index,
    rowWeight: row.weight,
    columnWeight: column.weight,
  }
}

/** Find the cell containing a value and how far into it the value sits. */
function cell(axis: number[], value: number) {
  const last = axis.length - 2
  if (axis.length < 2) return { index: 0, weight: 0 }

  let index = 0
  while (index < last && axis[index + 1] < value) index += 1

  const span = axis[index + 1] - axis[index]
  const weight = span === 0 ? 0 : (value - axis[index]) / span

  return { index, weight: Math.min(1, Math.max(0, weight)) }
}

/**
 * Estimate how far along the route the rider is at a given time.
 *
 * Interpolates between the arrival times the analysis produced, so it follows
 * the same gradient-aware speed estimate rather than assuming a flat pace.
 */
export function distanceAtTime(segments: Segment[], time: Date): number | null {
  const known = segments
    .filter((segment) => segment.time !== null)
    .map((segment) => ({
      at: new Date(segment.time as string).getTime(),
      km: segment.mid_distance_km,
    }))

  if (known.length === 0) return null

  const target = time.getTime()
  if (target <= known[0].at) return known[0].km
  if (target >= known[known.length - 1].at) return known[known.length - 1].km

  for (let i = 0; i < known.length - 1; i += 1) {
    const from = known[i]
    const to = known[i + 1]
    if (target <= to.at) {
      const span = to.at - from.at
      const weight = span === 0 ? 0 : (target - from.at) / span
      return from.km + (to.km - from.km) * weight
    }
  }
  return known[known.length - 1].km
}

/** Position along a polyline at a given distance, in kilometres. */
export function positionAtDistance(
  route: [number, number][],
  distanceKm: number,
): [number, number] | null {
  if (route.length === 0) return null
  if (route.length === 1) return route[0]

  const target = Math.max(0, distanceKm) * 1000
  let covered = 0

  for (let i = 0; i < route.length - 1; i += 1) {
    const step = haversine(route[i], route[i + 1])
    if (covered + step >= target) {
      const weight = step === 0 ? 0 : (target - covered) / step
      return [
        route[i][0] + (route[i + 1][0] - route[i][0]) * weight,
        route[i][1] + (route[i + 1][1] - route[i][1]) * weight,
      ]
    }
    covered += step
  }
  return route[route.length - 1]
}

/** Great-circle distance between two points in metres. */
function haversine([lat1, lon1]: [number, number], [lat2, lon2]: [number, number]): number {
  const radius = 6_371_000
  const toRad = Math.PI / 180
  const dLat = (lat2 - lat1) * toRad
  const dLon = (lon2 - lon1) * toRad

  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1 * toRad) * Math.cos(lat2 * toRad) * Math.sin(dLon / 2) ** 2

  return 2 * radius * Math.asin(Math.min(1, Math.sqrt(a)))
}
