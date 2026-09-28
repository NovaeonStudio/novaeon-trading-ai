/**
 * App languages: English (bundled, also the fallback), German and Romanian (loaded on demand).
 *
 * Components use `$t` / `useI18n()`; plain TypeScript helpers import `t` from here. Numbers, money and dates are
 * formatted with `intlLocale()` so separators follow the chosen language.
 */
import { createI18n } from 'vue-i18n';
import en from '@/locales/en.json';

export const APP_LOCALES = ['en', 'de', 'ro'] as const;
export type AppLocale = (typeof APP_LOCALES)[number];

/** Language names in their own language (for the picker). */
export const LOCALE_NAMES: Record<AppLocale, string> = {
  en: 'English',
  de: 'Deutsch',
  ro: 'Română',
};

const INTL_LOCALES: Record<AppLocale, string> = {
  en: 'en-US',
  de: 'de-DE',
  ro: 'ro-RO',
};

const loaders: Record<Exclude<AppLocale, 'en'>, () => Promise<{ default: unknown }>> = {
  de: () => import('@/locales/de.json'),
  ro: () => import('@/locales/ro.json'),
};

/**
 * Romanian has three plural forms: one (1 tranzacție), few (2–19 tranzacții) and other (20 de tranzacții).
 * Messages with three variants use "one | few | other"; two variants use "one | other" like English and German.
 */
function romanianPlural(choice: number, choicesLength: number): number {
  const cat = new Intl.PluralRules('ro-RO').select(Math.abs(choice));
  if (choicesLength >= 3) return cat === 'one' ? 0 : cat === 'few' ? 1 : 2;
  return cat === 'one' ? 0 : 1;
}

type MessageSchema = typeof en;

export const i18n = createI18n<[MessageSchema], AppLocale, false>({
  legacy: false,
  globalInjection: true,
  locale: 'en',
  fallbackLocale: 'en',
  // German and Romanian are added by setLocale() when first used.
  messages: { en } as Record<AppLocale, MessageSchema>,
  pluralRules: { ro: romanianPlural },
  missingWarn: false,
  fallbackWarn: false,
});

type Named = Record<string, unknown>;
/** Translate outside components (utils, stores): t(key), t(key, count), t(key, named), t(key, named, count). */
export const t: {
  (key: string): string;
  (key: string, plural: number): string;
  (key: string, named: Named): string;
  (key: string, named: Named, plural: number): string;
} = (...args: unknown[]) => (i18n.global.t as unknown as (...a: unknown[]) => string)(...args);
export const te = (key: string): boolean => i18n.global.te(key);

export function isAppLocale(value: unknown): value is AppLocale {
  return typeof value === 'string' && (APP_LOCALES as readonly string[]).includes(value);
}

/** Browser language if it is German or Romanian, else English. */
export function detectLocale(): AppLocale {
  const langs =
    typeof navigator === 'undefined' ? [] : (navigator.languages ?? [navigator.language]);
  for (const l of langs) {
    const base = (l ?? '').toLowerCase().split('-')[0];
    if (base === 'en') return 'en';
    if (isAppLocale(base)) return base;
  }
  return 'en';
}

/** The active app language. Reactive (reads the i18n locale ref). */
export function currentLocale(): AppLocale {
  const l = i18n.global.locale.value;
  return isAppLocale(l) ? l : 'en';
}

/** BCP 47 tag for Intl formatting in the active language (en-US, de-DE, ro-RO). Reactive. */
export function intlLocale(): string {
  return INTL_LOCALES[currentLocale()];
}

/** Load the messages for a language (once) and switch to it; also sets <html lang>. */
export async function setLocale(locale: AppLocale): Promise<void> {
  if (locale !== 'en' && !i18n.global.availableLocales.includes(locale)) {
    const mod = await loaders[locale]();
    i18n.global.setLocaleMessage(locale, mod.default as MessageSchema);
  }
  i18n.global.locale.value = locale;
  if (typeof document !== 'undefined') document.documentElement.lang = locale;
}
