import type { de } from './de'

// Makes t() reject keys that do not exist in the resources.
declare module 'i18next' {
  interface CustomTypeOptions {
    defaultNS: 'translation'
    resources: {
      translation: typeof de
    }
  }
}
