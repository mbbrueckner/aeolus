export type Alignment = 'headwind' | 'crosswind' | 'tailwind'
export type RainTier = 'light' | 'moderate' | 'heavy'

export interface Segment {
  coordinates: [number, number][]
  point: [number, number]
  time: string | null
  distance_km: number
  bearing_deg: number
  wind_speed_km_h: number
  wind_direction_deg: number
  wind_gusts_km_h: number
  precipitation_mm_h: number
  rain_tier: RainTier | null
  alignment: Alignment
  tailwind_km_h: number
  crosswind_km_h: number
  score: number
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

export interface Analysis {
  summary: Summary
  segments: Segment[]
}

export interface AnalyseRequest {
  gpx: File
  avgSpeedKmh: number
  startTime: string
}
