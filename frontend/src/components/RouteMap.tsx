import { useEffect, useMemo } from 'react'
import { MapContainer, Marker, Polyline, Popup, TileLayer, useMap } from 'react-leaflet'
import L from 'leaflet'
import type { Analysis, Segment } from '../types'
import { distanceAtTime, positionAtDistance, windOnRoute } from '../field'
import {
  ALIGNMENT_COLOUR,
  ALIGNMENT_LABEL,
  RAIN_COLOUR,
  RAIN_LABEL,
  arrowRotation,
  formatTime,
  isNotable,
  segmentColour,
} from '../wind'
import { RainOverlay } from './RainOverlay'
import { TimeSlider } from './TimeSlider'
import { WindArrows } from './WindArrows'

interface Props {
  analysis: Analysis
  slot: number
  onSlotChange: (slot: number) => void
  playing: boolean
  onPlayingChange: (playing: boolean) => void
}

export function RouteMap({ analysis, slot, onSlotChange, playing, onPlayingChange }: Props) {
  const { field, segments, route } = analysis

  const rideStart = firstTime(segments)
  const rideEnd = lastTime(segments)
  const shownTime = field ? new Date(field.slots[slot] * 1000) : null
  const riderPosition = useMemo(() => {
    if (!shownTime) return null
    const km = distanceAtTime(segments, shownTime)
    return km === null ? null : positionAtDistance(route, km)
  }, [route, segments, shownTime?.getTime()])

  const atRideTime = Boolean(
    shownTime && rideStart && rideEnd && shownTime >= rideStart && shownTime <= rideEnd,
  )

  return (
    <div className="relative h-full w-full">
      <MapContainer center={[48.14, 11.58]} zoom={11} scrollWheelZoom className="h-full w-full">
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        />

        {field && <RainOverlay field={field} slot={slot} />}
        {field && <WindArrows field={field} slot={slot} />}

        {segments.map((segment, index) => (
          <Polyline
            key={`line-${index}`}
            positions={segment.coordinates}
            pathOptions={{
              color: colourAt(analysis, segment, slot),
              weight: 6,
              opacity: 0.92,
              dashArray: segment.unsafe ? '10 8' : undefined,
            }}
          />
        ))}

        {segments.map((segment, index) => (
          <Marker key={`arrow-${index}`} position={segment.point} icon={pinIcon(segment)}>
            <Popup>
              <SegmentPopup segment={segment} />
            </Popup>
          </Marker>
        ))}

        {riderPosition && <Marker position={riderPosition} icon={riderIcon(atRideTime)} />}

        <FitToRoute segments={segments} />
      </MapContainer>

      <Legend />

      {field && field.slots.length > 1 && (
        <TimeSlider
          field={field}
          slot={slot}
          onSlotChange={onSlotChange}
          playing={playing}
          onPlayingChange={onPlayingChange}
          rideStart={rideStart}
          rideEnd={rideEnd}
        />
      )}
    </div>
  )
}

/** Colour a stretch by the wind at the displayed time, not at arrival. */
function colourAt(analysis: Analysis, segment: Segment, slot: number): string {
  if (!analysis.field) return segmentColour(segment)

  const [lat, lon] = segment.point
  const wind = windOnRoute(analysis.field, lat, lon, slot, segment.bearing_deg)

  if (Math.max(Math.abs(wind.headwindKmH), wind.crosswindKmH) < 12) return '#94a3b8'
  return ALIGNMENT_COLOUR[wind.alignment]
}

function Legend() {
  return (
    <div className="pointer-events-none absolute top-3 right-3 z-1000 rounded-box border border-base-300/60 bg-base-100/92 px-3.5 py-2.5 text-xs shadow-lg backdrop-blur-sm">
      <p className="mb-1.5 font-medium opacity-55">Wind auf der Route</p>
      <ul className="space-y-1">
        {(['headwind', 'crosswind', 'tailwind'] as const).map((alignment) => (
          <li key={alignment} className="flex items-center gap-2">
            <span
              className="h-1 w-6 rounded-full"
              style={{ background: ALIGNMENT_COLOUR[alignment] }}
            />
            {ALIGNMENT_LABEL[alignment]}
          </li>
        ))}
        <li className="flex items-center gap-2 opacity-60">
          <span className="h-1 w-6 rounded-full bg-slate-400" />
          kaum Wind
        </li>
      </ul>

      <p className="mt-2.5 mb-1.5 font-medium opacity-55">Niederschlag</p>
      <div className="flex items-center gap-1.5">
        <span
          className="h-2.5 w-16 rounded-full"
          style={{
            background: `linear-gradient(90deg, ${RAIN_COLOUR.light}, ${RAIN_COLOUR.moderate}, ${RAIN_COLOUR.heavy})`,
          }}
        />
        <span className="opacity-60">leicht → stark</span>
      </div>
    </div>
  )
}

function SegmentPopup({ segment }: { segment: Segment }) {
  return (
    <div className="min-w-52 text-sm">
      <div className="mb-2 flex items-baseline justify-between gap-3">
        <span className="font-semibold">
          {segment.time ? formatTime(segment.time) : `km ${segment.mid_distance_km.toFixed(1)}`}
        </span>
        <span className="opacity-55">
          {segment.time ? `bei km ${segment.mid_distance_km.toFixed(1)}` : 'Streckenabschnitt'}
        </span>
      </div>

      {segment.wind_speed_km_h === null ? (
        <p className="text-xs leading-relaxed opacity-55">
          Gib Abfahrtszeit und Schnitt an, um zu sehen, was dich hier erwartet. Die Karte
          zeigt derweil das Wetter zur eingestellten Uhrzeit.
        </p>
      ) : (
        <>
          <dl className="space-y-1">
            <Row
              label="Wind"
              value={`${segment.wind_speed_km_h.toFixed(0)} km/h`}
              accent={isNotable(segment) && segment.alignment ? ALIGNMENT_COLOUR[segment.alignment] : undefined}
              note={isNotable(segment) && segment.alignment ? ALIGNMENT_LABEL[segment.alignment] : 'schwach'}
            />
            <Row label="Böen" value={`${(segment.wind_gusts_km_h ?? 0).toFixed(0)} km/h`} />
            <Row
              label="Regen"
              value={segment.rain_tier ? `${(segment.precipitation_mm_h ?? 0).toFixed(1)} mm/h` : 'trocken'}
              accent={segment.rain_tier ? RAIN_COLOUR[segment.rain_tier] : undefined}
              note={segment.rain_tier ? RAIN_LABEL[segment.rain_tier] : undefined}
            />
          </dl>
          <p className="mt-2 text-[11px] opacity-45">Werte für deine geschätzte Ankunft hier.</p>
        </>
      )}

      {segment.unsafe && (
        <p className="mt-1.5 rounded-md bg-error/15 px-2 py-1 text-xs font-medium text-error">
          Kritische Bedingungen
        </p>
      )}
    </div>
  )
}

function Row({
  label,
  value,
  note,
  accent,
}: {
  label: string
  value: string
  note?: string
  accent?: string
}) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="opacity-55">{label}</dt>
      <dd className="text-right font-medium" style={accent ? { color: accent } : undefined}>
        {value}
        {note && <span className="ml-1 text-xs font-normal opacity-70">{note}</span>}
      </dd>
    </div>
  )
}

/** Pan and zoom so the whole route is visible whenever it changes. */
function FitToRoute({ segments }: { segments: Segment[] }) {
  const map = useMap()

  const bounds = useMemo(() => {
    const points = segments.flatMap((segment) => segment.coordinates)
    return points.length ? L.latLngBounds(points) : null
  }, [segments])

  useEffect(() => {
    if (bounds) map.fitBounds(bounds, { padding: [40, 60] })
  }, [bounds, map])

  return null
}

/** A small marker at each forecast point along the route. */
function pinIcon(segment: Segment): L.DivIcon {
  const colour =
    isNotable(segment) && segment.alignment ? ALIGNMENT_COLOUR[segment.alignment] : '#64748b'
  const rotation = arrowRotation(segment.wind_direction_deg ?? 0)

  return L.divIcon({
    className: '',
    iconSize: [22, 22],
    iconAnchor: [11, 11],
    html: `
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none"
           style="transform:rotate(${rotation}deg);filter:drop-shadow(0 1px 2px oklch(0% 0 0 / .35))">
        <circle cx="12" cy="12" r="10" fill="var(--color-base-100)" opacity="0.9"/>
        <path d="M12 5.5 L12 18 M12 5.5 L8.5 10 M12 5.5 L15.5 10"
              stroke="${colour}" stroke-width="2.6"
              stroke-linecap="round" stroke-linejoin="round"/>
      </svg>`,
  })
}

/** Where the rider would be at the displayed time. */
function riderIcon(onRoute: boolean): L.DivIcon {
  const size = 30
  return L.divIcon({
    className: '',
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    html: `
      <div style="display:grid;place-items:center;width:${size}px;height:${size}px;
                  opacity:${onRoute ? 1 : 0.35};transition:opacity .2s;">
        <span style="position:absolute;width:${size}px;height:${size}px;border-radius:9999px;
                     background:var(--color-primary);opacity:.22;"></span>
        <span style="width:13px;height:13px;border-radius:9999px;
                     background:var(--color-primary);
                     border:2.5px solid var(--color-base-100);
                     box-shadow:0 1px 4px oklch(0% 0 0 / .4);"></span>
      </div>`,
  })
}

function firstTime(segments: Segment[]): Date | null {
  const found = segments.find((segment) => segment.time)
  return found?.time ? new Date(found.time) : null
}

function lastTime(segments: Segment[]): Date | null {
  for (let i = segments.length - 1; i >= 0; i -= 1) {
    if (segments[i].time) return new Date(segments[i].time as string)
  }
  return null
}
