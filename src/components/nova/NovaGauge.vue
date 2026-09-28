<script setup lang="ts">
/** Buffer gauge: how much of a budget is used. The bar fill carries severity (profit → warn → loss). */
const props = withDefaults(
  defineProps<{
    label: string;
    value: number;
    display: string;
    sub?: string;
    warnAt?: number;
    badAt?: number;
  }>(),
  { sub: undefined, warnAt: 0.5, badAt: 0.8 },
);
const { t } = useI18n();
const { tokens } = useNovaChartTheme();
const clamped = computed(() => Math.min(1, Math.max(0, props.value)));
const level = computed<'ok' | 'warn' | 'bad'>(() =>
  clamped.value >= props.badAt ? 'bad' : clamped.value >= props.warnAt ? 'warn' : 'ok',
);
const color = computed(() =>
  level.value === 'bad'
    ? tokens.value.loss
    : level.value === 'warn'
      ? tokens.value.warn
      : tokens.value.profit,
);
const status = computed(() =>
  level.value === 'bad'
    ? t('stat.gauge.bad')
    : level.value === 'warn'
      ? t('stat.gauge.warn')
      : t('stat.gauge.ok'),
);
</script>

<template>
  <div class="min-w-0">
    <div class="flex items-center justify-between gap-2">
      <span class="nova-label truncate">{{ label }}</span>
      <span class="inline-flex shrink-0 items-center gap-1.5 text-xs text-muted">
        <span class="size-1.5 rounded-full" :style="{ backgroundColor: color }" />
        {{ status }}
      </span>
    </div>
    <div class="nova-num mt-1 text-xl font-semibold tracking-tight text-highlighted">
      {{ display }}
    </div>
    <div
      class="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-accented"
      role="meter"
      :aria-label="label"
      :aria-valuenow="Math.round(clamped * 100)"
      aria-valuemin="0"
      aria-valuemax="100"
    >
      <div
        class="h-full rounded-full transition-[width] duration-300 ease-[cubic-bezier(0.32,0.72,0,1)]"
        :style="{ width: `${clamped * 100}%`, backgroundColor: color }"
      />
    </div>
    <div v-if="sub" class="nova-num mt-2 text-xs text-pretty text-muted">{{ sub }}</div>
  </div>
</template>
