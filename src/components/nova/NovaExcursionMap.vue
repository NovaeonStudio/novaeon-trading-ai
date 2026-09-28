<script setup lang="ts">
import type { EChartsOption, ScatterSeriesOption } from 'echarts';
import ECharts from 'vue-echarts';
import { ScatterChart } from 'echarts/charts';
import {
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  TooltipComponent,
} from 'echarts/components';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import type { ClosedTrade } from '@/types';
import { I18nT } from 'vue-i18n';
import { excursion } from '@/utils/novaMetrics';

use([
  ScatterChart,
  CanvasRenderer,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  MarkLineComponent,
]);

/** MAE (x, how far a trade went against us) vs MFE (y, best run) per closed trade, colored by result. */
const props = defineProps<{ trades: ClosedTrade[] }>();

const { chartTheme, tokens } = useNovaChartTheme();
const { t: tr } = useI18n();

interface Dot {
  value: number[];
  name: string;
  realized: number;
  win: boolean;
}

const data = computed<Dot[]>(() =>
  props.trades
    .map((t) => ({ t, e: excursion(t) }))
    .filter((r) => r.e)
    .map(({ t, e }) => ({
      value: [Number(((e?.mae ?? 0) * 100).toFixed(2)), Number(((e?.mfe ?? 0) * 100).toFixed(2))],
      name: t.pair.split('/')[0] ?? t.pair,
      realized: (t.profit_ratio ?? 0) * 100,
      win: (t.profit_abs ?? 0) >= 0,
    })),
);

const efficiency = computed(() => {
  const rows = props.trades
    .map((t) => ({ t, e: excursion(t) }))
    .filter((r) => r.e && (r.e.mfe ?? 0) > 0);
  if (!rows.length) return null;
  const captured = rows.map(({ t, e }) => Math.max(-1, (t.profit_ratio ?? 0) / (e?.mfe as number)));
  return captured.reduce((s, v) => s + v, 0) / captured.length;
});

const option = computed((): EChartsOption => {
  const t = tokens.value;
  const winnerName = tr('excursion.winner');
  const loserName = tr('excursion.loser');
  const minMae = Math.min(0, ...data.value.map((d) => d.value[0] ?? 0));
  const maxMfe = Math.max(0, ...data.value.map((d) => d.value[1] ?? 0));
  const reach = Math.min(-minMae, maxMfe);
  const dots = (win: boolean, name: string): ScatterSeriesOption => ({
    type: 'scatter',
    name,
    symbolSize: 10,
    color: win ? t.profit : t.loss,
    itemStyle: { borderColor: t.surface, borderWidth: 2, opacity: 0.9 },
    emphasis: { scale: 1.6, itemStyle: { opacity: 1 } },
    data: data.value.filter((d) => d.win === win),
  });
  const winners = dots(true, winnerName);
  if (reach > 0) {
    // Reference: a run as large as the drawdown (1 : 1).
    winners.markLine = {
      silent: true,
      symbol: 'none',
      animation: false,
      lineStyle: { color: t.axis, type: 'solid', width: 1 },
      label: { formatter: '1 : 1', position: 'end', ...novaLineLabel(t) },
      data: [[{ coord: [0, 0] }, { coord: [-reach, reach] }]],
    };
  }
  return {
    grid: novaGrid({ top: 32 }),
    legend: { top: 0, right: 0, data: [winnerName, loserName] },
    tooltip: {
      trigger: 'item',
      formatter: (p) => {
        const d = (p as { data: Dot }).data;
        const c = d.win ? t.profit : t.loss;
        return (
          novaTooltipTitle(t, d.name) +
          novaTooltipRow(t, c, tr('excursion.closedAt'), `${d.realized.toFixed(2)}%`) +
          novaTooltipRow(t, t.axis, tr('excursion.worstDrawdown'), `${d.value[0]}%`) +
          novaTooltipRow(t, t.axis, tr('excursion.bestRun'), `${d.value[1]}%`)
        );
      },
    },
    xAxis: {
      type: 'value',
      name: tr('excursion.axisMae'),
      nameLocation: 'middle',
      nameGap: 28,
      max: 0,
    },
    yAxis: {
      type: 'value',
      name: tr('excursion.axisMfe'),
      nameLocation: 'middle',
      nameGap: 36,
      min: 0,
    },
    series: [winners, dots(false, loserName)],
  };
});
</script>

<template>
  <div class="flex h-full flex-col">
    <div class="min-h-64 flex-1">
      <div
        v-if="!data.length"
        class="flex h-full flex-col items-center justify-center gap-3 text-center"
      >
        <span class="flex size-10 items-center justify-center rounded-full bg-accented">
          <UIcon name="i-mdi-scatter-plot-outline" class="size-5 text-muted" />
        </span>
        <p class="text-sm text-pretty text-muted">{{ tr('excursion.empty') }}</p>
      </div>
      <ECharts v-else :option="option" :theme="chartTheme" autoresize class="h-full w-full" />
    </div>
    <I18nT
      v-if="efficiency !== null"
      keypath="excursion.efficiency"
      tag="p"
      scope="global"
      class="nova-num mt-3 text-xs text-pretty text-muted"
    >
      <template #pct>
        <span class="font-medium text-highlighted">{{ novaPct(efficiency, 0) }}</span>
      </template>
    </I18nT>
  </div>
</template>
