import { useEffect, useRef } from 'react'
import { useMap } from 'react-leaflet'
import L from 'leaflet'
import { sampleField } from '../field'
import type { Field } from '../types'

interface Props {
  field: Field
  slot: number
}

/** Pixels along the longer edge of the rendered field. */
const RESOLUTION = 320

/**
 * Colour stops for the rain scale, in mm/h.
 *
 * Kept translucent throughout so the map underneath stays readable — this is a
 * forecast interpolated from a coarse grid, not a radar image, and it should
 * not look more certain than it is.
 */
const STOPS: { mmH: number; rgba: [number, number, number, number] }[] = [
  { mmH: 0.2, rgba: [125, 211, 252, 0] },
  { mmH: 0.6, rgba: [125, 211, 252, 90] },
  { mmH: 2.5, rgba: [56, 189, 248, 135] },
  { mmH: 6.0, rgba: [37, 99, 235, 165] },
  { mmH: 15.0, rgba: [79, 70, 229, 190] },
  { mmH: 30.0, rgba: [126, 34, 206, 205] },
]

export function RainOverlay({ field, slot }: Props) {
  const map = useMap()
  const overlayRef = useRef<L.ImageOverlay | null>(null)

  useEffect(() => {
    const bounds = L.latLngBounds(
      [field.latitudes[0], field.longitudes[0]],
      [field.latitudes[field.latitudes.length - 1], field.longitudes[field.longitudes.length - 1]],
    )
    const url = render(field, slot)

    if (!url) {
      overlayRef.current?.remove()
      overlayRef.current = null
      return
    }

    if (overlayRef.current) {
      overlayRef.current.setUrl(url)
      overlayRef.current.setBounds(bounds)
    } else {
      overlayRef.current = L.imageOverlay(url, bounds, {
        opacity: 1,
        interactive: false,
        zIndex: 200,
      }).addTo(map)
    }
  }, [field, slot, map])

  useEffect(() => {
    return () => {
      overlayRef.current?.remove()
      overlayRef.current = null
    }
  }, [])

  return null
}

/** Draw the rain field to a data URL, or null when nothing is falling. */
function render(field: Field, slot: number): string | null {
  const rows = field.latitudes.length
  const columns = field.longitudes.length

  let wettest = 0
  for (let row = 0; row < rows; row += 1) {
    for (let column = 0; column < columns; column += 1) {
      wettest = Math.max(wettest, field.precipitation_mm_h[row][column][slot])
    }
  }
  if (wettest < STOPS[0].mmH) return null

  const aspect = columns / rows
  const width = Math.round(aspect >= 1 ? RESOLUTION : RESOLUTION * aspect)
  const height = Math.round(aspect >= 1 ? RESOLUTION / aspect : RESOLUTION)

  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const context = canvas.getContext('2d')
  if (!context) return null

  const image = context.createImageData(width, height)
  const south = field.latitudes[0]
  const north = field.latitudes[rows - 1]
  const west = field.longitudes[0]
  const east = field.longitudes[columns - 1]

  for (let y = 0; y < height; y += 1) {
    // Image rows run north to south, the grid runs south to north.
    const lat = north - ((north - south) * y) / (height - 1)
    for (let x = 0; x < width; x += 1) {
      const lon = west + ((east - west) * x) / (width - 1)
      const { precipitationMmH } = sampleField(field, lat, lon, slot)
      const [r, g, b, a] = colourFor(precipitationMmH)

      const offset = (y * width + x) * 4
      image.data[offset] = r
      image.data[offset + 1] = g
      image.data[offset + 2] = b
      image.data[offset + 3] = a
    }
  }

  context.putImageData(image, 0, 0)
  return canvas.toDataURL()
}

/** Interpolate the rain colour scale at a given rate. */
function colourFor(mmH: number): [number, number, number, number] {
  if (mmH <= STOPS[0].mmH) return [0, 0, 0, 0]
  if (mmH >= STOPS[STOPS.length - 1].mmH) return STOPS[STOPS.length - 1].rgba

  for (let i = 0; i < STOPS.length - 1; i += 1) {
    const from = STOPS[i]
    const to = STOPS[i + 1]
    if (mmH <= to.mmH) {
      const weight = (mmH - from.mmH) / (to.mmH - from.mmH)
      return [
        Math.round(from.rgba[0] + (to.rgba[0] - from.rgba[0]) * weight),
        Math.round(from.rgba[1] + (to.rgba[1] - from.rgba[1]) * weight),
        Math.round(from.rgba[2] + (to.rgba[2] - from.rgba[2]) * weight),
        Math.round(from.rgba[3] + (to.rgba[3] - from.rgba[3]) * weight),
      ]
    }
  }
  return STOPS[STOPS.length - 1].rgba
}
