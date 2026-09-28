<script setup lang="ts">
import { useClipboard } from '@vueuse/core';

withDefaults(
  defineProps<{
    content: string | string[];
    isValid?: boolean;
  }>(),
  {
    isValid: true,
  },
);

const { copy, isSupported, copied } = useClipboard();
const { t } = useI18n();
</script>

<template>
  <div class="copy-container group relative">
    <button
      v-if="isSupported && isValid"
      type="button"
      class="absolute end-2 top-2 flex items-center gap-1 rounded-lg bg-elevated px-2 py-1 text-xs text-muted opacity-0 transition-opacity duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] group-hover:opacity-100 hover:text-highlighted focus:opacity-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-400/60"
      :aria-label="copied ? t('common.copied') : t('general.copyToClipboard')"
      @click="copy(typeof content === 'string' ? content : JSON.stringify(content))"
    >
      <span v-if="copied">{{ t('common.copied') }}</span>
      <UIcon :name="copied ? 'i-mdi-check-circle' : 'i-mdi-content-copy'" class="size-4" />
    </button>
    <pre
      class="m-0 overflow-auto rounded-xl border border-default/70 bg-default p-3 text-start text-xs"
    ><code>{{ content }}</code></pre>
  </div>
</template>
