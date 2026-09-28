<script setup lang="ts">
/** Compact cockpit position row: coin, leverage, P&L, stop→now ruler, distance to stop, age. */
import type { Trade } from '@/types';
import { distanceToStop } from '@/utils/novaMetrics';

const props = defineProps<{ trade: Trade }>();
defineEmits<{ open: [trade: Trade] }>();
const { t: tr } = useI18n();

const t = computed(() => props.trade);
const up = computed(() => (t.value.profit_abs ?? 0) >= 0);
const ruler = computed(() => {
  const cur = t.value.current_rate ?? t.value.open_rate;
  const pts = [t.value.stop_loss_abs, t.value.open_rate, cur, t.value.max_rate].filter(
    (v): v is number => typeof v === 'number' && v > 0,
  );
  const lo = Math.min(...pts);
  const hi = Math.max(...pts);
  const pos = (v?: number) => (v && hi > lo ? ((v - lo) / (hi - lo)) * 100 : 50);
  return { entry: pos(t.value.open_rate), now: pos(cur), best: pos(t.value.max_rate) };
});
</script>

<template>
  <button
    type="button"
    class="grid w-full grid-cols-[minmax(0,6rem)_minmax(3rem,1fr)_auto_4rem] items-center gap-3 rounded-xl px-3 py-2 text-left transition duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] hover:bg-accented/60 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-400/60 active:scale-[0.98]"
    @click="$emit('open', t)"
  >
    <span class="flex min-w-0 items-center gap-2">
      <span class="truncate font-semibold text-highlighted">{{ t.pair.split('/')[0] }}</span>
      <span
        class="nova-num shrink-0 rounded-full px-2 py-0.5 text-xs font-medium"
        :class="
          (t.leverage ?? 1) > 1
            ? 'bg-brand-400/15 text-brand-600 dark:text-brand-300'
            : 'bg-accented text-muted'
        "
        >{{ t.leverage ?? 1 }}x</span
      >
    </span>
    <span class="relative h-4" aria-hidden="true">
      <span class="absolute inset-x-0 top-1/2 h-1 -translate-y-1/2 rounded-full bg-accented" />
      <span class="absolute top-0 h-4 w-0.5 rounded-full bg-rose-400/80" style="left: 0%" />
      <span
        class="absolute top-1/2 h-1 -translate-y-1/2 rounded-full"
        :class="up ? 'bg-emerald-500/70' : 'bg-rose-500/70'"
        :style="{
          left: `${Math.min(ruler.entry, ruler.now)}%`,
          width: `${Math.abs(ruler.now - ruler.entry)}%`,
        }"
      />
      <span
        class="absolute top-1 h-2 w-0.5 -translate-x-1/2 rounded-full bg-emerald-300/60"
        :style="{ left: `${ruler.best}%` }"
      />
      <span
        class="absolute top-1/2 size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-default"
        :class="up ? 'bg-emerald-400' : 'bg-rose-400'"
        :style="{ left: `${ruler.now}%` }"
      />
    </span>
    <span
      class="nova-num text-right text-sm font-semibold"
      :class="up ? 'text-emerald-400' : 'text-rose-400'"
    >
      {{ novaPct(t.profit_ratio, 2, true) }}
    </span>
    <span class="nova-num text-right text-xs leading-tight">
      <span class="block text-default" :title="tr('positions.row.distanceToStop')">{{
        novaPct(distanceToStop(t), 1)
      }}</span>
      <span class="block text-dimmed" :title="tr('positions.row.heldFor')">{{
        novaAge(t.open_timestamp)
      }}</span>
    </span>
  </button>
</template>
