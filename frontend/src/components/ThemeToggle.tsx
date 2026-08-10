import type { ThemePreference } from '../theme'

interface Props {
  preference: ThemePreference
  onChange: (preference: ThemePreference) => void
}

const OPTIONS: { value: ThemePreference; label: string; icon: string }[] = [
  { value: 'light', label: 'Hell', icon: 'M12 3v1.5M12 19.5V21M4.2 4.2l1.1 1.1M18.7 18.7l1.1 1.1M3 12h1.5M19.5 12H21M4.2 19.8l1.1-1.1M18.7 5.3l1.1-1.1' },
  { value: 'system', label: 'System', icon: 'M3.5 5.5h17v10h-17zM9 19.5h6M12 15.5v4' },
  { value: 'dark', label: 'Dunkel', icon: 'M20 14.2A8.2 8.2 0 1 1 9.8 4a6.6 6.6 0 0 0 10.2 10.2z' },
]

export function ThemeToggle({ preference, onChange }: Props) {
  return (
    <div
      role="radiogroup"
      aria-label="Farbschema"
      className="inline-flex gap-0.5 rounded-full bg-base-200 p-0.5"
    >
      {OPTIONS.map((option) => {
        const active = preference === option.value
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={active}
            aria-label={option.label}
            title={option.label}
            onClick={() => onChange(option.value)}
            className={`grid size-7 place-items-center rounded-full transition-colors ${
              active
                ? 'bg-base-100 text-base-content shadow-sm'
                : 'text-base-content/45 hover:text-base-content/80'
            }`}
          >
            <svg
              width="15"
              height="15"
              viewBox="0 0 24 24"
              fill={option.value === 'dark' ? 'currentColor' : 'none'}
              stroke="currentColor"
              strokeWidth="1.7"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              {option.value === 'light' && <circle cx="12" cy="12" r="3.8" />}
              <path d={option.icon} />
            </svg>
          </button>
        )
      })}
    </div>
  )
}
