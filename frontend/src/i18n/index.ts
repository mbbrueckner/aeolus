import i18n from 'i18next'
import LanguageDetector from 'i18next-browser-languagedetector'
import { initReactI18next } from 'react-i18next'
import { de } from './de'
import { en } from './en'

export const LANGUAGES = ['de', 'en'] as const
export type Language = (typeof LANGUAGES)[number]

const STORAGE_KEY = 'aeolus:language'

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      de: { translation: de },
      en: { translation: en },
    },
    fallbackLng: 'en',
    supportedLngs: LANGUAGES,
    // "de-AT" and the like should land on German rather than the fallback.
    nonExplicitSupportedLngs: true,
    detection: {
      order: ['localStorage', 'navigator'],
      lookupLocalStorage: STORAGE_KEY,
      caches: ['localStorage'],
    },
    interpolation: {
      // React escapes for us; doing it twice mangles anything with an ampersand.
      escapeValue: false,
    },
  })

/** Keep the document's language in step, for screen readers and hyphenation. */
i18n.on('languageChanged', (language) => {
  document.documentElement.lang = language
})

export default i18n
