import { useEffect, useMemo } from 'react'
import { MapContainer, Marker, Polyline, Popup, TileLayer, useMap } from 'react-leaflet'
import L from 'leaflet'
import type { Segment } from '../types'
import {
  ALIGNMENT_COLOUR,
  ALIGNMENT_LABEL,
  arrowRotation,
  formatTime,
  isNotable,
  segmentColour,
} from '../wind'

interface Props {
  segments: Segment[]
}

export function RouteMap({ segments }: Props) {
  return (
    <MapContainer
      center={[48.14, 11.58]}
      zoom={11}
      scrollWheelZoom
      className="h-full w-full"
    >
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
      />

      {segments.map((segment, index) => (
        <Polyline
          key={`line-${index}`}
          positions={segment.coordinates}
          pathOptions={{
            color: segmentColour(segment),
            weight: 6,
            opacity: 0.85,
            dashArray: segment.unsafe ? '10 8' : undefined,
          }}
        />
      ))}

      {segments.map((segment, index) => (
        <Marker
          key={`arrow-${index}`}
          position={segment.point}
          icon={windIcon(segment)}
        >
          <Popup>
            <SegmentPopup segment={segment} />
          </Popup>
        </Marker>
      ))}

      <FitToRoute segments={segments} />
    </MapContainer>
  )
}

function SegmentPopup({ segment }: { segment: Segment }) {
  return (
    <div className="min-w-48 text-sm">
      <div className="mb-2 flex items-baseline justify-between gap-3">
        <span className="font-semibold">{formatTime(segment.time)}</span>
        <span className="opacity-60">{segment.distance_km.toFixed(1)} km</span>
      </div>

      <dl className="space-y-1">
        <Row
          label="Wind"
          value={`${segment.wind_speed_km_h.toFixed(0)} km/h`}
          accent={isNotable(segment) ? ALIGNMENT_COLOUR[segment.alignment] : undefined}
          note={isNotable(segment) ? ALIGNMENT_LABEL[segment.alignment] : 'schwach'}
        />
        <Row label="Böen" value={`${segment.wind_gusts_km_h.toFixed(0)} km/h`} />
        {segment.precipitation_mm_h > 0.05 && (
          <Row label="Regen" value={`${segment.precipitation_mm_h.toFixed(1)} mm/h`} />
        )}
      </dl>

      {segment.unsafe && (
        <p className="mt-2 rounded bg-error/15 px-2 py-1 text-xs font-medium text-error">
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
      <dt className="opacity-60">{label}</dt>
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
    if (bounds) {
      map.fitBounds(bounds, { padding: [40, 40] })
    }
  }, [bounds, map])

  return null
}

/** An arrow pointing where the wind is blowing, labelled with its speed. */
function windIcon(segment: Segment): L.DivIcon {
  const colour = isNotable(segment) ? ALIGNMENT_COLOUR[segment.alignment] : '#64748b'
  const rotation = arrowRotation(segment.wind_direction_deg)
  const wet = segment.precipitation_mm_h >= 0.4

  return L.divIcon({
    className: '',
    iconSize: [46, 46],
    iconAnchor: [23, 23],
    html: `
      <div style="display:flex;flex-direction:column;align-items:center;line-height:1;gap:1px;">
        <svg width="26" height="26" viewBox="0 0 24 24" fill="none"
             style="transform:rotate(${rotation}deg);filter:drop-shadow(0 1px 2px oklch(0% 0 0 / .3))">
          <path d="M12 3 L12 21 M12 3 L7 9 M12 3 L17 9"
                stroke="${colour}" stroke-width="3.2"
                stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <span style="font-size:10px;font-weight:600;color:${colour};
                     background:color-mix(in oklch, var(--color-base-100) 85%, transparent);
                     border-radius:4px;padding:1px 4px;white-space:nowrap;
                     box-shadow:0 1px 3px oklch(0% 0 0 / .18);">
          ${segment.wind_speed_km_h.toFixed(0)}${wet ? ' ☔' : ''}
        </span>
      </div>`,
  })
}
