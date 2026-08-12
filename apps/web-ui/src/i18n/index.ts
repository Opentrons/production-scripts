import { computed } from 'vue'
import { createI18n, useI18n } from 'vue-i18n'
import enUS from './locales/en-US'
import zhCN from './locales/zh-CN'

export const APP_LOCALE_STORAGE_KEY = 'production-platform-locale'
const LEGACY_DASHBOARD_LOCALE_KEY = 'production-platform-dashboard-language'

export type AppLocale = 'zh-CN' | 'en-US'

export function normalizeLocale(value: unknown): AppLocale | null {
  if (typeof value !== 'string') return null
  const normalized = value.trim().toLowerCase().replace('_', '-')
  if (normalized === 'zh' || normalized.startsWith('zh-')) return 'zh-CN'
  if (normalized === 'en' || normalized.startsWith('en-')) return 'en-US'
  return null
}

function readStoredLocale(): AppLocale | null {
  if (typeof window === 'undefined') return null
  try {
    return normalizeLocale(window.localStorage.getItem(APP_LOCALE_STORAGE_KEY))
      || normalizeLocale(window.localStorage.getItem(LEGACY_DASHBOARD_LOCALE_KEY))
  } catch {
    return null
  }
}

export function detectInitialLocale(): AppLocale {
  return readStoredLocale()
    || normalizeLocale(typeof navigator === 'undefined' ? null : navigator.language)
    || 'zh-CN'
}

export const i18n = createI18n({
  legacy: false,
  locale: detectInitialLocale(),
  fallbackLocale: 'zh-CN',
  messages: {
    'zh-CN': zhCN,
    'en-US': enUS,
  },
  missingWarn: import.meta.env.DEV,
  fallbackWarn: import.meta.env.DEV,
})

export function currentLocale(): AppLocale {
  return normalizeLocale(i18n.global.locale.value) || 'zh-CN'
}

export function setAppLocale(locale: AppLocale): void {
  const changed = i18n.global.locale.value !== locale
  i18n.global.locale.value = locale
  if (typeof document !== 'undefined') document.documentElement.lang = locale
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(APP_LOCALE_STORAGE_KEY, locale)
    window.localStorage.removeItem(LEGACY_DASHBOARD_LOCALE_KEY)
  } catch {
    // Language switching remains available when storage is blocked.
  }
  if (changed) window.dispatchEvent(new CustomEvent('production-platform-locale-change', { detail: locale }))
}

export function useAppLocale() {
  const { locale, t, d, n } = useI18n({ useScope: 'global' })
  const appLocale = computed<AppLocale>(() => normalizeLocale(locale.value) || 'zh-CN')
  const isChinese = computed(() => appLocale.value === 'zh-CN')
  const setLocale = (nextLocale: AppLocale) => setAppLocale(nextLocale)
  return { locale: appLocale, isChinese, setLocale, t, d, n }
}

setAppLocale(detectInitialLocale())
