<script setup lang="ts">
import { APP_LOCALES, LOCALE_NAMES, currentLocale } from '@/i18n';

/** Language picker (English / Deutsch / Română). Saved per browser in the settings store. */
const settingsStore = useSettingsStore();
const { t } = useI18n();

const active = computed(() => currentLocale());
</script>

<template>
  <div
    class="nova-seg grid! w-full grid-cols-3 text-sm"
    role="group"
    :aria-label="t('common.language')"
  >
    <button
      v-for="l in APP_LOCALES"
      :key="l"
      type="button"
      class="min-h-10 min-w-0 truncate px-2 font-medium"
      :lang="l"
      :aria-pressed="active === l"
      @click="settingsStore.language = l"
    >
      {{ LOCALE_NAMES[l] }}
    </button>
  </div>
</template>
