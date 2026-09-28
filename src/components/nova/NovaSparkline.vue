<script setup lang="ts">
/** Tiny, axis-free line for consumer views (Simple mode Home). One accent line, soft accent wash, end dot. */
const props = defineProps<{ values: number[]; label?: string }>();
const { t } = useI18n();
const ariaLabel = computed(() => props.label ?? t('stat.sparkline.label'));

const { tokens } = useNovaChartTheme();
const washId = `nova-spark-${useId()}`;

const W = 100;
const H = 40;
const PAD = 3;

const geom = computed(() => {
  const v = props.values.filter((x) => Number.isFinite(x));
  if (v.length < 2) return null;
  const lo = Math.min(...v);
  const hi = Math.max(...v);
  const span = hi - lo || Math.abs(hi) * 0.01 || 1;
  const pts = v.map((y, i) => [
    (i / (v.length - 1)) * W,
    PAD + (1 - (y - lo) / span) * (H - PAD * 2),
  ]);
  const line = pts.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(2)},${y.toFixed(2)}`).join(' ');
  const last = pts[pts.length - 1] ?? [W, H / 2];
  return {
    line,
    area: `${line} L${W},${H} L0,${H} Z`,
    endX: (last[0]! / W) * 100,
    endY: (last[1]! / H) * 100,
  };
});
</script>

<template>
  <div class="relative" role="img" :aria-label="ariaLabel">
    <template v-if="geom">
      <svg :viewBox="`0 0 ${W} ${H}`" preserveAspectRatio="none" class="h-full w-full">
        <defs>
          <linearGradient :id="washId" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" :stop-color="tokens.accent" stop-opacity="0.2" />
            <stop offset="100%" :stop-color="tokens.accent" stop-opacity="0" />
          </linearGradient>
        </defs>
        <path :d="geom.area" :fill="`url(#${washId})`" />
        <path
          :d="geom.line"
          fill="none"
          :stroke="tokens.accent"
          stroke-width="2"
          stroke-linejoin="round"
          stroke-linecap="round"
          vector-effect="non-scaling-stroke"
        />
      </svg>
      <span
        class="absolute size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full"
        :style="{
          left: `${geom.endX}%`,
          top: `${geom.endY}%`,
          backgroundColor: tokens.accent,
          boxShadow: '0 0 0 2px var(--ui-bg)',
        }"
      />
    </template>
    <div
      v-else
      class="flex h-full flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-default p-4 text-center"
    >
      <span class="flex size-10 items-center justify-center rounded-full bg-accented">
        <UIcon name="i-mdi-chart-line" class="size-5 text-muted" />
      </span>
      <p class="text-sm text-pretty text-muted">
        <slot name="empty">{{ t('stat.sparkline.empty') }}</slot>
      </p>
    </div>
  </div>
</template>
