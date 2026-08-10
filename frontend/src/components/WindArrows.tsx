import { useMemo } from 'react'
import { Marker } from 'react-leaflet'
import L from 'leaflet'
import { sampleField, windDirectionDeg, windSpeedKmH } from '../field'
import type { Field } from '../types'

interface Props {
  field: Field
  slot: number
}

/** Roughly how many arrows to show, whatever the grid's resolution. */
const TARGET_ARROWS = 55
const CALM_KM_H = 3

export function WindArrows({ field, slot }: Props) {
  const arrows = useMemo(() => {
    const rows = field.latitudes.length
    const columns = field.longitudes.length
    const step = Math.max(1, Math.round(Math.sqrt((rows * columns) / TARGET_ARROWS)))

    const placed: { lat: number; lon: number; speed: number; direction: number }[] = []
    for (let row = 0; row < rows; row += step) {
      for (let column = 0; column < columns; column += step) {
        const lat = field.latitudes[row]
        const lon = field.longitudes[column]
        const sample = sampleField(field, lat, lon, slot)
        placed.push({
          lat,
          lon,
          speed: windSpeedKmH(sample),
          direction: windDirectionDeg(sample),
        })
      }
    }
    return placed
  }, [field, slot])

  return (
    <>
      {arrows.map((arrow, index) =>
        arrow.speed >= CALM_KM_H ? (
          <Marker
            key={index}
            position={[arrow.lat, arrow.lon]}
            icon={arrowIcon(arrow.speed, arrow.direction)}
            interactive={false}
            zIndexOffset={-500}
          />
        ) : null,
      )}
    </>
  )
}

/**
 * A barb pointing the way the wind blows, growing with speed.
 *
 * Drawn deliberately faint: this is the background field, and it must not
 * compete with the route it sits behind.
 */
function arrowIcon(speedKmH: number, directionDeg: number): L.DivIcon {
  const rotation = (directionDeg + 180) % 360
  const scale = Math.min(1.5, 0.55 + speedKmH / 38)
  const size = Math.round(26 * scale)
  const opacity = Math.min(0.62, 0.26 + speedKmH / 60)

  return L.divIcon({
    className: '',
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    html: `
      <svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none"
           style="transform:rotate(${rotation}deg);opacity:${opacity.toFixed(2)};
                  color:var(--color-base-content);">
        <path d="M12 4.5 L12 19.5 M12 4.5 L8 9.5 M12 4.5 L16 9.5"
              stroke="currentColor" stroke-width="2.4"
              stroke-linecap="round" stroke-linejoin="round"/>
      </svg>`,
  })
}
