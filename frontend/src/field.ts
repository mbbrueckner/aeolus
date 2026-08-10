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

/** Index of the slot covering a moment, clamped to the field's range. */
export function slotIndexAt(field: Field, time: Date): number {
  const unix = time.getTime() / 1000
  let nearest = 0
  let best = Infinity

  for (let i = 0; i < field.slots.length; i += 1) {
    const distance = Math.abs(field.slots[i] - unix)
    if (distance < best) {
      best = distance
      nearest = i
    }
  }
  return nearest
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

  const read = (grid: number[][][]) => {
    const topLeft = grid[row][column][slot]
    const topRight = grid[row][column + 1][slot]
    const bottomLeft = grid[row + 1][column][slot]
    const bottomRight = grid[row + 1][column + 1][slot]

    const top = topLeft + (topRight - topLeft) * columnWeight
    const bottom = bottomLeft + (bottomRight - bottomLeft) * columnWeight
    return top + (bottom - top) * rowWeight
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
