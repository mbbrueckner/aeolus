export type Alignment = 'headwind' | 'crosswind' | 'tailwind'

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
