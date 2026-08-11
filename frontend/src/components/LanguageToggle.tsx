import { useTranslation } from 'react-i18next'
import { LANGUAGES } from '../i18n'

export function LanguageToggle() {
  const { t, i18n } = useTranslation()
  const active = LANGUAGES.find((language) => i18n.resolvedLanguage === language)

  return (
    <div
      role="radiogroup"
      aria-label={t('language.label')}
      className="inline-flex gap-0.5 rounded-full bg-base-200 p-0.5"
    >
      {LANGUAGES.map((language) => (
        <button
          key={language}
          type="button"
          role="radio"
          aria-checked={active === language}
          onClick={() => void i18n.changeLanguage(language)}
          className={`rounded-full px-1.5 py-0.5 text-[10px] font-semibold uppercase transition-colors ${
            active === language
              ? 'bg-base-100 text-base-content shadow-sm'
              : 'text-base-content/40 hover:text-base-content/70'
          }`}
        >
          {language}
        </button>
      ))}
    </div>
  )
}
