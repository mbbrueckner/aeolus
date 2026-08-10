export type Alignment = 'headwind' | 'crosswind' | 'tailwind'
export type RainTier = 'light' | 'moderate' | 'heavy'

export interface Segment {
  coordinates: [number, number][]
  point: [number, number]
  time: string | null
  distance_km: number
  start_distance_km: number
  mid_distance_km: number
  bearing_deg: number
  // Filled only when a departure time and speed were given.
  wind_speed_km_h: number | null
  wind_direction_deg: number | null
  wind_gusts_km_h: number | null
  precipitation_mm_h: number | null
  rain_tier: RainTier | null
  alignment: Alignment | null
  tailwind_km_h: number | null
  crosswind_km_h: number | null
  score: number | null
  unsafe: boolean
}

export interface Summary {
  total_distance_km: number
  headwind_km: number
  tailwind_km: number
  crosswind_km: number
  rain_km: number
  light_rain_km: number
  moderate_rain_km: number
  heavy_rain_km: number
  rain_start_km: number | null
  rain_start_time: string | null
  max_precipitation_mm_h: number
  unsafe_km: number
  headwind_share: number
  tailwind_share: number
  rain_share: number
  mean_wind_km_h: number
  max_gust_km_h: number
  score: number
  arrival: string | null
}

/** Forecast weather on a grid over time, shaped [row][column][slot]. */
export interface Field {
  latitudes: number[]
  longitudes: number[]
  slots: number[]
  precipitation_mm_h: number[][][]
  wind_u_m_s: number[][][]
  wind_v_m_s: number[][][]
  wind_gusts_m_s: number[][][]
  precipitation_probability: number[][][]
}

export interface Analysis {
  route: [number, number][]
  summary: Summary | null
  segments: Segment[]
  field: Field | null
}

export interface AnalyseRequest {
  gpx: File
  avgSpeedKmh?: number
  startTime?: string
}
