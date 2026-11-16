import { createI18n } from 'vue-i18n'
import de from './locales/de.json'
import en from './locales/en.json'
import es from './locales/es.json'
import ja from './locales/ja.json'
import ptBR from './locales/pt-BR.json'

export const DEFAULT_LOCALE = 'en' as const

export const supportedLocales = [
  { value: 'en', label: 'English' },
  { value: 'ja', label: '日本語' },
  { value: 'de', label: 'Deutsch' },
  { value: 'pt-BR', label: 'Português (Brasil)' },
  { value: 'es', label: 'Español' },
] as const

export type AppLocale = (typeof supportedLocales)[number]['value']

export const i18n = createI18n({
  legacy: false,
  globalInjection: true,
  locale: DEFAULT_LOCALE,
  fallbackLocale: DEFAULT_LOCALE,
  messages: {
    en,
    ja,
    de,
    'pt-BR': ptBR,
    es,
  },
})

export function setAppLocale(locale: AppLocale): AppLocale {
  i18n.global.locale.value = locale
  document.documentElement.lang = locale
  return locale
}

