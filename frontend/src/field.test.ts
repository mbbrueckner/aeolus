import { describe, expect, it } from 'vitest'
import {
  distanceAtTime,
  headwindKmH,
  positionAtDistance,
  sampleField,
  slotIndexAt,
  windDirectionDeg,
  timeAtSlot,
  windOnRoute,
  windSpeedKmH,
} from './field'
import type { Field, Segment } from './types'

const SLOT = 1_770_000_000

/** A two-by-two grid whose corners can carry different values. */
function makeField(
  corners: [number, number, number, number] = [0, 0, 0, 0],
  wind: { u: number; v: number } = { u: 0, v: 0 },
  slots = 1,
): Field {
  const grid = (values: [number, number, number, number]) => [
    [Array(slots).fill(values[0]), Array(slots).fill(values[1])],
    [Array(slots).fill(values[2]), Array(slots).fill(values[3])],
  ]

  return {
    latitudes: [48.0, 49.0],
    longitudes: [11.0, 12.0],
    slots: Array.from({ length: slots }, (_, i) => SLOT + i * 900),
    precipitation_mm_h: grid(corners),
    wind_u_m_s: grid([wind.u, wind.u, wind.u, wind.u]),
    wind_v_m_s: grid([wind.v, wind.v, wind.v, wind.v]),
    wind_gusts_m_s: grid([0, 0, 0, 0]),
    precipitation_probability: grid([0, 0, 0, 0]),
  }
}

function segment(time: string, midKm: number): Segment {
  return {
    coordinates: [],
    point: [48, 11],
    time,
    distance_km: 1,
    start_distance_km: midKm - 0.5,
    mid_distance_km: midKm,
    bearing_deg: 90,
    wind_speed_km_h: 0,
    wind_direction_deg: 0,
    wind_gusts_km_h: 0,
    precipitation_mm_h: 0,
    rain_tier: null,
    alignment: 'crosswind',
    tailwind_km_h: 0,
    crosswind_km_h: 0,
    score: 0,
    unsafe: false,
  }
}

describe('sampleField', () => {
  it('returns the corner value at a corner', () => {
    const field = makeField([1, 2, 3, 4])
    expect(sampleField(field, 48.0, 11.0, 0).precipitationMmH).toBeCloseTo(1)
    expect(sampleField(field, 49.0, 12.0, 0).precipitationMmH).toBeCloseTo(4)
  })

  it('averages the four corners at the centre', () => {
    const field = makeField([0, 0, 4, 4])
    expect(sampleField(field, 48.5, 11.5, 0).precipitationMmH).toBeCloseTo(2)
  })

  it('interpolates along one axis only when the other is constant', () => {
    const field = makeField([0, 10, 0, 10])
    expect(sampleField(field, 48.0, 11.25, 0).precipitationMmH).toBeCloseTo(2.5)
  })

  it('clamps outside the grid rather than extrapolating', () => {
    const field = makeField([1, 1, 5, 5])
    expect(sampleField(field, 40.0, 11.0, 0).precipitationMmH).toBeCloseTo(1)
    expect(sampleField(field, 60.0, 11.0, 0).precipitationMmH).toBeCloseTo(5)
  })
})

describe('wind vectors', () => {
  it('reports speed from the components', () => {
    expect(windSpeedKmH({ windU: 3, windV: 4, precipitationMmH: 0, gustsMs: 0 })).toBeCloseTo(
      5 * 3.6,
    )
  })

  it('reads an eastward vector as wind from the west', () => {
    const direction = windDirectionDeg({ windU: 5, windV: 0, precipitationMmH: 0, gustsMs: 0 })
    expect(direction).toBeCloseTo(270)
  })

  it('reads a southward vector as wind from the north', () => {
    const direction = windDirectionDeg({ windU: 0, windV: -5, precipitationMmH: 0, gustsMs: 0 })
    expect(direction).toBeCloseTo(0)
  })

  it('counts wind blowing against travel as a headwind', () => {
    // Riding east, wind blowing west.
    const wind = headwindKmH({ windU: -5, windV: 0, precipitationMmH: 0, gustsMs: 0 }, 90)
    expect(wind).toBeCloseTo(5 * 3.6)
  })

  it('counts wind blowing with travel as a tailwind', () => {
    const wind = headwindKmH({ windU: 5, windV: 0, precipitationMmH: 0, gustsMs: 0 }, 90)
    expect(wind).toBeCloseTo(-5 * 3.6)
  })

  it('cancels for wind across the direction of travel', () => {
    const wind = headwindKmH({ windU: 0, windV: 5, precipitationMmH: 0, gustsMs: 0 }, 90)
    expect(wind).toBeCloseTo(0)
  })
})

describe('windOnRoute', () => {
  it('classifies a pure headwind', () => {
    const field = makeField([0, 0, 0, 0], { u: -5, v: 0 })
    const wind = windOnRoute(field, 48.5, 11.5, 0, 90)

    expect(wind.alignment).toBe('headwind')
    expect(wind.headwindKmH).toBeCloseTo(18)
  })

  it('classifies a pure tailwind', () => {
    const field = makeField([0, 0, 0, 0], { u: 5, v: 0 })
    expect(windOnRoute(field, 48.5, 11.5, 0, 90).alignment).toBe('tailwind')
  })

  it('classifies a pure crosswind', () => {
    const field = makeField([0, 0, 0, 0], { u: 0, v: 5 })
    const wind = windOnRoute(field, 48.5, 11.5, 0, 90)

    expect(wind.alignment).toBe('crosswind')
    expect(wind.crosswindKmH).toBeCloseTo(18)
  })

  it('reverses when the rider turns around', () => {
    const field = makeField([0, 0, 0, 0], { u: -5, v: 0 })
    const out = windOnRoute(field, 48.5, 11.5, 0, 90)
    const back = windOnRoute(field, 48.5, 11.5, 0, 270)

    expect(out.headwindKmH).toBeCloseTo(-back.headwindKmH)
  })
})

describe('slotIndexAt', () => {
  it('finds the matching slot', () => {
    const field = makeField([0, 0, 0, 0], { u: 0, v: 0 }, 4)
    expect(slotIndexAt(field, new Date((SLOT + 1800) * 1000))).toBe(2)
  })

  it('clamps before the first slot', () => {
    const field = makeField([0, 0, 0, 0], { u: 0, v: 0 }, 4)
    expect(slotIndexAt(field, new Date((SLOT - 100000) * 1000))).toBe(0)
  })

  it('clamps after the last slot', () => {
    const field = makeField([0, 0, 0, 0], { u: 0, v: 0 }, 4)
    expect(slotIndexAt(field, new Date((SLOT + 100000) * 1000))).toBe(3)
  })
})

describe('distanceAtTime', () => {
  const segments = [
    segment('2026-08-12T10:00:00Z', 2),
    segment('2026-08-12T11:00:00Z', 22),
  ]

  it('interpolates between arrival times', () => {
    expect(distanceAtTime(segments, new Date('2026-08-12T10:30:00Z'))).toBeCloseTo(12)
  })

  it('holds at the start before departure', () => {
    expect(distanceAtTime(segments, new Date('2026-08-12T08:00:00Z'))).toBeCloseTo(2)
  })

  it('holds at the end after arrival', () => {
    expect(distanceAtTime(segments, new Date('2026-08-12T20:00:00Z'))).toBeCloseTo(22)
  })

  it('returns null without any timed segment', () => {
    expect(distanceAtTime([], new Date())).toBeNull()
  })
})

describe('positionAtDistance', () => {
  const route: [number, number][] = [
    [48.0, 11.0],
    [48.0, 11.1],
  ]

  it('starts at the first point', () => {
    expect(positionAtDistance(route, 0)).toEqual([48.0, 11.0])
  })

  it('ends at the last point when overshooting', () => {
    expect(positionAtDistance(route, 999)).toEqual([48.0, 11.1])
  })

  it('lands halfway at half the distance', () => {
    const total = 111.32 * 0.1 * Math.cos((48 * Math.PI) / 180)
    const halfway = positionAtDistance(route, total / 2)

    expect(halfway?.[1]).toBeCloseTo(11.05, 2)
  })

  it('returns null for an empty route', () => {
    expect(positionAtDistance([], 5)).toBeNull()
  })
})

describe('time interpolation', () => {
  it('blends between the two quarter hours around a fractional slot', () => {
    const field = makeField([0, 0, 0, 0], { u: 0, v: 0 }, 2)
    field.precipitation_mm_h = [
      [[0, 10], [0, 10]],
      [[0, 10], [0, 10]],
    ]
    expect(sampleField(field, 48.5, 11.5, 0.5).precipitationMmH).toBeCloseTo(5)
    expect(sampleField(field, 48.5, 11.5, 0.25).precipitationMmH).toBeCloseTo(2.5)
  })

  it('matches the stored value on a whole slot', () => {
    const field = makeField([0, 0, 0, 0], { u: 0, v: 0 }, 2)
    field.precipitation_mm_h = [
      [[3, 9], [3, 9]],
      [[3, 9], [3, 9]],
    ]
    expect(sampleField(field, 48.5, 11.5, 0).precipitationMmH).toBeCloseTo(3)
    expect(sampleField(field, 48.5, 11.5, 1).precipitationMmH).toBeCloseTo(9)
  })

  it('clamps past the last slot instead of running off the end', () => {
    const field = makeField([0, 0, 0, 0], { u: 0, v: 0 }, 2)
    field.precipitation_mm_h = [
      [[3, 9], [3, 9]],
      [[3, 9], [3, 9]],
    ]
    expect(sampleField(field, 48.5, 11.5, 5).precipitationMmH).toBeCloseTo(9)
  })
})

describe('slot positions are continuous', () => {
  it('returns a fraction between slots', () => {
    const field = makeField([0, 0, 0, 0], { u: 0, v: 0 }, 4)
    // 450 s is half of a 900 s slot.
    expect(slotIndexAt(field, new Date((SLOT + 450) * 1000))).toBeCloseTo(0.5)
  })

  it('round trips through timeAtSlot', () => {
    const field = makeField([0, 0, 0, 0], { u: 0, v: 0 }, 4)
    const moment = new Date((SLOT + 1350) * 1000)
    const slot = slotIndexAt(field, moment)

    expect(timeAtSlot(field, slot).getTime()).toBe(moment.getTime())
  })

  it('gives a minute of clock time per sixtieth of a slot', () => {
    const field = makeField([0, 0, 0, 0], { u: 0, v: 0 }, 4)
    const start = timeAtSlot(field, 0).getTime()
    const oneMinute = timeAtSlot(field, 1 / 15).getTime()

    expect(oneMinute - start).toBe(60_000)
  })
})
