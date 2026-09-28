<script setup lang="ts">
import * as uiLocales from '@nuxt/ui/locale';
import { currentLocale, detectLocale, isAppLocale, setLocale } from '@/i18n';

const settingsStore = useSettingsStore();
const colorStore = useColorStore();
const botStore = useBotStore();
const route = useRoute();
const showSidebar = computed(() => botStore.hasBots && route.path !== '/login');
onMounted(() => {
  setTimezone(settingsStore.timezone);
  colorStore.updateProfitLossColor();
});
watch(
  () => settingsStore.language,
  (lang) => setLocale(isAppLocale(lang) ? lang : detectLocale()),
);
/** Nuxt UI's own texts (close buttons, date pickers, …) follow the app language. */
const uiLocale = computed(() => uiLocales[currentLocale()]);
const { t } = useI18n();
watch(
  () => settingsStore.timezone,
  (tz) => {
    console.log('timezone changed', tz);
    setTimezone(tz);
  },
);
</script>

<template>
  <UApp :locale="uiLocale">
    <div id="app" class="flex flex-col h-dvh" :style="colorStore.cssVars">
      <a
        href="#main-content"
        class="sr-only focus:not-sr-only focus:fixed focus:start-3 focus:top-3 focus:z-50 focus:rounded-xl focus:bg-elevated focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-highlighted focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-400/60"
        >{{ t('common.skipToContent') }}</a
      >
      <NavBar />
      <div class="flex min-h-0 grow">
        <NovaSidebar v-if="showSidebar" class="hidden md:flex" />
        <BodyLayout class="min-w-0 grow overflow-auto" />
      </div>
      <NavFooter />
    </div>
  </UApp>
</template>

<style scoped>
#app {
  font-family: var(--font-sans);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-align: center;
}

/* * {
  outline: 1px solid #f00 !important;
} */
</style>
