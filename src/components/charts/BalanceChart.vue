<script setup lang="ts">
import type { EChartsOption } from 'echarts';
import ECharts from 'vue-echarts';

import { PieChart } from 'echarts/charts';
import {
  DatasetComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
} from 'echarts/components';
import { use } from 'echarts/core';
import { LabelLayout } from 'echarts/features';
import { CanvasRenderer } from 'echarts/renderers';

import type { BalanceValues } from '@/types';
import { intlLocale } from '@/i18n';

use([
  PieChart,
  CanvasRenderer,
  DatasetComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
  LabelLayout,
]);

const balanceChart = ref(null);
const { width } = useElementSize(balanceChart);

const props = withDefaults(
  defineProps<{
    currencies: BalanceValues[];
    showTitle?: boolean;
  }>(),
  {
    showTitle: true,
  },
);
const { chartTheme, tokens } = useNovaChartTheme();
// `t` is the chart theme tokens below, so the translate function is `tr`.
const { t: tr } = useI18n();

const balanceChartOptions = computed((): EChartsOption => {
  const t = tokens.value;
  return {
    title: {
      text: tr('charts.balance.title'),
      show: props.showTitle,
    },
    dataset: {
      dimensions: ['balance', 'currency', 'est_stake', 'free', 'used', 'stake'],
      source: props.currencies,
    },
    tooltip: {
      trigger: 'item',
      formatter: (params) => {
        const v = params.value as BalanceValues;
        return (
          novaTooltipTitle(t, v.currency) +
          novaTooltipRow(
            t,
            String(params.color),
            tr('charts.balance.balance'),
            formatPriceCurrency(v.balance, v.currency, 8),
          ) +
          novaTooltipRow(
            t,
            String(params.color),
            tr('charts.balance.shareOfWallet', {
              pct: Number(params.percent).toLocaleString(intlLocale(), {
                maximumFractionDigits: 2,
              }),
            }),
            formatPriceCurrency(v.est_stake, v.stake),
          )
        );
      },
    },
    // legend: {
    //   orient: 'vertical',
    //   right: 10,
    //   top: 20,
    //   bottom: 20,
    // },
    series: [
      {
        type: 'pie',
        radius: ['48%', '70%'],
        center: ['50%', '52%'],
        padAngle: 1,
        itemStyle: { borderRadius: 4, borderColor: t.surface, borderWidth: 2 },

        encode: {
          value: 'est_stake',
          itemName: 'currency',
          tooltip: ['balance', 'currency'],
        },
        label: {
          formatter: '{b} {d}%',
          color: t.textMuted,
          fontSize: 11,
        },
        labelLine: { lineStyle: { color: t.axis } },
        tooltip: {
          show: true,
        },
      },
    ],
  };
});
</script>

<template>
  <ECharts
    v-if="currencies"
    ref="balanceChart"
    :option="balanceChartOptions"
    :theme="chartTheme"
    :style="{ height: width * 0.6 + 'px' }"
    autoresize
  />
</template>

<style lang="css" scoped>
.echarts {
  min-height: 20px;
}
</style>
