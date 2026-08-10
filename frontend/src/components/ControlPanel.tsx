import { useState } from 'react'

interface Props {
  busy: boolean
  onSubmit: (gpx: File, avgSpeedKmh: number, startTime: string) => void
}

/** Local wall-clock time in the format a datetime-local input expects. */
function nowForInput(): string {
  const now = new Date()
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset(), 0, 0)
  return now.toISOString().slice(0, 16)
}

export function ControlPanel({ busy, onSubmit }: Props) {
  const [file, setFile] = useState<File | null>(null)
  const [speed, setSpeed] = useState(22)
  const [start, setStart] = useState(nowForInput)

  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault()
        if (file) onSubmit(file, speed, start)
      }}
    >
      <label className="form-control">
        <span className="mb-1 block text-sm font-medium">GPX-Datei</span>
        <input
          type="file"
          accept=".gpx"
          required
          className="file-input file-input-sm w-full"
          onChange={(event) => setFile(event.target.files?.[0] ?? null)}
        />
      </label>

      <label className="form-control">
        <span className="mb-1 flex items-baseline justify-between text-sm font-medium">
          Schnitt
          <span className="tabular-nums opacity-70">{speed.toFixed(1)} km/h</span>
        </span>
        <input
          type="range"
          min={10}
          max={45}
          step={0.5}
          value={speed}
          className="range range-primary range-xs"
          onChange={(event) => setSpeed(Number(event.target.value))}
        />
      </label>

      <label className="form-control">
        <span className="mb-1 block text-sm font-medium">Abfahrt</span>
        <input
          type="datetime-local"
          required
          value={start}
          className="input input-sm w-full"
          onChange={(event) => setStart(event.target.value)}
        />
      </label>

      <button type="submit" className="btn btn-primary w-full" disabled={!file || busy}>
        {busy && <span className="loading loading-spinner loading-sm" />}
        {busy ? 'Wetter wird geholt …' : 'Route auswerten'}
      </button>
    </form>
  )
}
