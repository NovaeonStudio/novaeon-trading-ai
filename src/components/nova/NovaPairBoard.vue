<script setup lang="ts">
import type { PerformanceEntry, Trade } from '@/types';

/** Realized profit per pair as diverging bars, with open-position markers. */
const props = defineProps<{
  performance: PerformanceEntry[];
  openTrades: Trade[];
  currency: string;
}>();
const emit = defineEmits<{ pair: [pair: string] }>();

const rows = computed(() => {
  const open = new Map(props.openTrades.map((t) => [t.pair, t]));
  const perf = [...props.performance].sort((a, b) => b.profit_abs - a.profit_abs);
  const maxAbs = Math.max(1e-9, ...perf.map((p) => Math.abs(p.profit_abs)));
  return perf.map((p) => ({
    pair: p.pair,
    name: p.pair.split('/')[0],
    profit: p.profit_abs,
    pct: p.profit_ratio,
    count: p.count,
    width: (Math.abs(p.profit_abs) / maxAbs) * 50,
    open: open.get(p.pair),
  }));
});
</script>

<template>
  <div v-if="!rows.length" class="flex items-center gap-3 py-2">
    <span class="flex size-10 shrink-0 items-center justify-center rounded-full bg-accented">
      <UIcon name="i-mdi-podium" class="size-5 text-muted" />
    </span>
    <p class="text-sm text-pretty text-muted">
      {{ $t('widgets.pairBoard.empty') }}
    </p>
  </div>
  <div v-else class="flex flex-col gap-0.5">
    <button
      v-for="r in rows"
      :key="r.pair"
      type="button"
      class="grid min-h-10 grid-cols-[5rem_minmax(0,1fr)_auto] items-center gap-3 rounded-lg px-2 py-1 text-left transition duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] hover:bg-accented/60 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-400/60 active:scale-[0.98]"
      :title="$t('widgets.pairBoard.openChart', { coin: r.name })"
      @click="emit('pair', r.pair)"
    >
      <span class="flex min-w-0 items-center gap-2 text-sm font-medium text-default">
        <span class="truncate">{{ r.name }}</span>
        <span
          v-if="r.open"
          class="size-1.5 shrink-0 rounded-full bg-brand-400"
          :title="$t('widgets.pairBoard.positionOpen')"
        />
      </span>
      <span class="relative h-1.5" aria-hidden="true">
        <span class="absolute inset-y-0 left-1/2 w-px bg-accented" />
        <span
          class="absolute inset-y-0 rounded-full"
          :class="r.profit >= 0 ? 'left-1/2 bg-emerald-500/80' : 'right-1/2 bg-rose-500/80'"
          :style="{ width: `${r.width}%` }"
        />
      </span>
      <span class="nova-num text-right text-xs whitespace-nowrap">
        <span
          class="nova-money font-medium"
          :class="r.profit >= 0 ? 'text-emerald-400' : 'text-rose-400'"
          >{{ novaMoney(r.profit, '', 2, true) }}</span
        >
        <span class="text-dimmed"> · {{ $t('widgets.pairBoard.trades', r.count) }}</span>
      </span>
    </button>
  </div>
</template>
