<script setup lang="ts">
/** Stat tile: quiet sentence-case label, the value (big, semibold), an optional sub line. */
import type { SampleQuality } from '@/utils/novaMetrics';

const props = withDefaults(
  defineProps<{
    label: string;
    value: string;
    sub?: string;
    tone?: 'pos' | 'neg' | 'neutral' | 'warn';
    money?: boolean;
    quality?: SampleQuality;
    hint?: string;
    size?: 'md' | 'lg';
  }>(),
  {
    sub: undefined,
    tone: 'neutral',
    money: false,
    quality: undefined,
    hint: undefined,
    size: 'md',
  },
);

const { t } = useI18n();

const toneClass = computed(
  () =>
    ({
      pos: 'text-emerald-400',
      neg: 'text-rose-400',
      warn: 'text-brand-400',
      neutral: 'text-highlighted',
    })[props.tone],
);
const qualityLabel = computed(() =>
  props.quality === 'early'
    ? t('stat.quality.early')
    : props.quality === 'low'
      ? t('stat.quality.low')
      : null,
);
</script>

<template>
  <div class="min-w-0" :title="hint">
    <div class="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
      <span class="nova-label truncate">{{ label }}</span>
      <span
        v-if="qualityLabel"
        class="rounded-full bg-accented/70 px-2 py-px text-xs text-dimmed"
        :title="t('stat.quality.hint')"
        >{{ qualityLabel }}</span
      >
    </div>
    <div
      class="mt-1 font-semibold tracking-tight"
      :class="[
        toneClass,
        size === 'lg' ? 'text-4xl' : 'text-2xl',
        { 'nova-money': money, 'opacity-60': quality === 'early' },
      ]"
    >
      {{ value }}
    </div>
    <div
      v-if="sub"
      class="nova-num mt-1 text-xs text-pretty text-muted"
      :class="{ 'nova-money': money }"
    >
      {{ sub }}
    </div>
  </div>
</template>
