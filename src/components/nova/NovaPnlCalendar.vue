<script setup lang="ts">
import { I18nT } from 'vue-i18n';
import { intlLocale } from '@/i18n';
import type { TimeSummaryRecord } from '@/types';

/** GitHub-style daily P&L heatmap (weeks as columns, Monday on top), diverging loss ↔ profit. */
const props = defineProps<{ days: TimeSummaryRecord[]; currency: string; weeks?: number }>();

const { tokens } = useNovaChartTheme();
const { t: tr } = useI18n();

/** Share of the pole color per step (1 = weakest … 4 = strongest); the midpoint is the neutral track. */
const STEPS = [0, 30, 55, 78, 100];
/** Short weekday names Monday … Sunday in the app language; only every other row is labeled. */
const weekdays = computed(() => {
  const fmt = new Intl.DateTimeFormat(intlLocale(), { weekday: 'short' });
  // 2024-01-01 was a Monday.
  return Array.from({ length: 7 }, (_, i) => (i % 2 ? '' : fmt.format(new Date(2024, 0, 1 + i))));
});
/** Short month names January … December in the app language. */
const months = computed(() => {
  const fmt = new Intl.DateTimeFormat(intlLocale(), { month: 'short' });
  return Array.from({ length: 12 }, (_, m) => fmt.format(new Date(2024, m, 1)));
});

interface Cell {
  key: string;
  date: Date;
  profit: number | null;
  trades: number;
  level: number;
  future: boolean;
}

function mix(color: string, pct: number): string {
  const t = tokens.value;
  return pct ? `color-mix(in oklab, ${color} ${pct}%, ${t.track})` : t.track;
}

const nWeeks = computed(() => props.weeks ?? 12);

const cells = computed<Cell[]>(() => {
  const byDate = new Map(props.days.map((d) => [d.date, d]));
  const today = new Date();
  const dow = (today.getDay() + 6) % 7; // Monday = 0
  const start = new Date(today);
  start.setDate(today.getDate() - dow - (nWeeks.value - 1) * 7);
  const maxAbs = Math.max(1e-9, ...props.days.map((d) => Math.abs(d.abs_profit)));
  const out: Cell[] = [];
  for (let i = 0; i < nWeeks.value * 7; i++) {
    const d = new Date(start);
    d.setDate(start.getDate() + i);
    const key = d.toISOString().slice(0, 10);
    const rec = byDate.get(key);
    const profit = rec ? rec.abs_profit : null;
    out.push({
      key,
      date: d,
      profit,
      trades: rec ? rec.trade_count : 0,
      level: profit ? Math.max(1, Math.ceil((Math.abs(profit) / maxAbs) * 4)) : 0,
      future: d > today,
    });
  }
  return out;
});

/** Month name above the first week column that starts a new month. */
const monthLabels = computed(() => {
  const labels: string[] = [];
  let prev = -1;
  for (let w = 0; w < nWeeks.value; w++) {
    const first = cells.value[w * 7];
    const m = first ? first.date.getMonth() : -1;
    const startsMonth = cells.value.slice(w * 7, w * 7 + 7).some((c) => c.date.getDate() === 1);
    labels.push(w === 0 || (startsMonth && m !== prev) ? (months.value[m] ?? '') : '');
    if (w === 0 || startsMonth) prev = m;
  }
  return labels;
});

function cellColor(c: Cell): string {
  const t = tokens.value;
  if (!c.profit) return t.track;
  return mix(c.profit > 0 ? t.profit : t.loss, STEPS[c.level] ?? 100);
}

function dateLabel(d: Date): string {
  return d.toLocaleDateString(intlLocale(), { weekday: 'short', month: 'short', day: 'numeric' });
}

function cellLabel(c: Cell): string {
  if (c.profit === null) return tr('calendar.cellEmpty', { date: dateLabel(c.date) });
  return tr(
    'calendar.cell',
    {
      date: dateLabel(c.date),
      profit: novaMoney(c.profit, props.currency, 2, true),
      n: c.trades,
    },
    c.trades,
  );
}

const totals = computed(() => {
  const vals = props.days.filter((d) => d.trade_count > 0);
  return {
    green: vals.filter((d) => d.abs_profit > 0).length,
    red: vals.filter((d) => d.abs_profit < 0).length,
    best: vals.length ? Math.max(...vals.map((d) => d.abs_profit)) : null,
    worst: vals.length ? Math.min(...vals.map((d) => d.abs_profit)) : null,
  };
});

/** Seven weekday rows, each with one cell per week. */
const rows = computed<Cell[][]>(() =>
  Array.from({ length: 7 }, (_, r) =>
    Array.from({ length: nWeeks.value }, (_, w) => cells.value[w * 7 + r]).filter(
      (c): c is Cell => !!c,
    ),
  ),
);

// Hover readout (one floating tooltip for the whole grid).
const hovered = ref<Cell | null>(null);
const tipPos = ref({ x: 0, y: 0 });
const gridRef = useTemplateRef<HTMLElement>('gridRef');

function show(c: Cell, ev: Event) {
  if (c.future) return;
  const el = ev.currentTarget as HTMLElement;
  const host = gridRef.value?.getBoundingClientRect();
  const r = el.getBoundingClientRect();
  if (!host) return;
  // Keep the readout inside the grid's width (it is ~9rem wide, centered on the cell).
  const x = Math.min(Math.max(r.left - host.left + r.width / 2, 72), Math.max(72, host.width - 72));
  tipPos.value = { x, y: r.top - host.top };
  hovered.value = c;
}
</script>

<template>
  <div class="min-w-0">
    <div>
      <div
        ref="gridRef"
        class="relative grid w-full max-w-md min-w-64 gap-1"
        :style="{ gridTemplateColumns: `auto repeat(${nWeeks}, minmax(0, 1fr))` }"
        @mouseleave="hovered = null"
      >
        <!-- month labels -->
        <span />
        <span
          v-for="(m, w) in monthLabels"
          :key="`m${w}`"
          class="h-4 overflow-visible text-xs whitespace-nowrap text-muted"
          >{{ m }}</span
        >
        <!-- rows: weekday label + one cell per week -->
        <template v-for="(row, r) in rows" :key="`r${r}`">
          <span class="self-center pe-1 text-xs leading-none text-muted">{{ weekdays[r] }}</span>
          <span
            v-for="c in row"
            :key="c.key"
            class="aspect-square rounded-[4px] transition duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] hover:ring-2 hover:ring-brand-400/60"
            :class="c.future ? 'invisible' : ''"
            :style="{ backgroundColor: cellColor(c) }"
            :aria-label="cellLabel(c)"
            role="img"
            @mouseenter="(e) => show(c, e)"
          />
        </template>

        <!-- floating readout -->
        <div
          v-if="hovered"
          class="pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-full rounded-xl border px-3 py-2 text-xs whitespace-nowrap shadow-lg"
          :style="{
            left: `${tipPos.x}px`,
            top: `${tipPos.y - 6}px`,
            backgroundColor: tokens.tooltipBg,
            borderColor: tokens.tooltipBorder,
          }"
        >
          <div class="text-muted">{{ dateLabel(hovered.date) }}</div>
          <div v-if="hovered.profit === null" class="mt-0.5 text-default">
            {{ tr('calendar.noTrades') }}
          </div>
          <div v-else class="mt-0.5 flex items-center gap-2">
            <span
              class="h-[3px] w-2.5 rounded-full"
              :style="{ backgroundColor: hovered.profit >= 0 ? tokens.profit : tokens.loss }"
            />
            <span class="nova-num nova-money font-semibold text-highlighted">{{
              novaMoney(hovered.profit, currency, 2, true)
            }}</span>
            <span class="text-muted">{{ tr('calendar.trades', hovered.trades) }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- scale legend -->
    <div class="mt-4 flex flex-wrap items-center justify-between gap-x-6 gap-y-3">
      <div class="flex items-center gap-1.5 text-xs text-muted" aria-hidden="true">
        <span class="me-1">{{ tr('calendar.loss') }}</span>
        <span
          v-for="s in [4, 3, 2, 1]"
          :key="`l${s}`"
          class="size-3 rounded-[3px]"
          :style="{ backgroundColor: mix(tokens.loss, STEPS[s] ?? 100) }"
        />
        <span class="size-3 rounded-[3px]" :style="{ backgroundColor: tokens.track }" />
        <span
          v-for="s in [1, 2, 3, 4]"
          :key="`p${s}`"
          class="size-3 rounded-[3px]"
          :style="{ backgroundColor: mix(tokens.profit, STEPS[s] ?? 100) }"
        />
        <span class="ms-1">{{ tr('calendar.profit') }}</span>
      </div>
      <div class="nova-num flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
        <span class="inline-flex items-center gap-1.5">
          <span class="size-1.5 rounded-full" :style="{ backgroundColor: tokens.profit }" />
          <I18nT keypath="calendar.greenDays" tag="span" scope="global">
            <template #n>
              <span class="font-medium text-highlighted">{{ totals.green }}</span>
            </template>
          </I18nT>
        </span>
        <span class="inline-flex items-center gap-1.5">
          <span class="size-1.5 rounded-full" :style="{ backgroundColor: tokens.loss }" />
          <I18nT keypath="calendar.redDays" tag="span" scope="global">
            <template #n>
              <span class="font-medium text-highlighted">{{ totals.red }}</span>
            </template>
          </I18nT>
        </span>
        <I18nT keypath="calendar.best" tag="span" scope="global">
          <template #value>
            <span class="nova-money font-medium text-highlighted">{{
              novaMoney(totals.best, '', 2, true)
            }}</span>
          </template>
        </I18nT>
        <I18nT keypath="calendar.worst" tag="span" scope="global">
          <template #value>
            <span class="nova-money font-medium text-highlighted">{{
              novaMoney(totals.worst, '', 2, true)
            }}</span>
          </template>
        </I18nT>
      </div>
    </div>
  </div>
</template>
