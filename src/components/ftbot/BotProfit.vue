<script setup lang="ts">
import type { AllProfitStats } from '@/types';

const props = defineProps<{
  profitAll: AllProfitStats;
  stakeCurrency: string;
  stakeCurrencyDecimals: number;
}>();

const { t } = useI18n();

const profit = computed(() => {
  if (!props.profitAll?.short) {
    return props.profitAll.all;
  }
  return props.profitAll[selectedOption.value];
});

const profitItems = computed(() => {
  if (!profit.value) return [];
  return [
    {
      metric: t('bot.profit.roiClosed'),
      value: profit.value.profit_closed_coin
        ? `${formatPriceCurrency(
            profit.value.profit_closed_coin,
            props.stakeCurrency,
            props.stakeCurrencyDecimals,
          )} (${formatPercent(profit.value.profit_closed_ratio_mean, 2)})`
        : t('bot.na'),
      // (&sum; ${formatPercent(profit.value.profit_closed_ratio_sum,  2,)})`
    },
    {
      metric: t('bot.profit.roiAll'),
      value: profit.value.profit_all_coin
        ? `${formatPriceCurrency(
            profit.value.profit_all_coin,
            props.stakeCurrency,
            props.stakeCurrencyDecimals,
          )} (${formatPercent(profit.value.profit_all_ratio_mean, 2)})`
        : t('bot.na'),
      //  (&sum; ${formatPercent(profit.value.profit_all_ratio_sum,2,)})`
    },

    {
      metric: t('bot.profit.tradeCount'),
      value: `${profit.value.trade_count ?? 0}`,
    },
    {
      metric: t('bot.profit.botStarted'),
      value: profit.value.bot_start_timestamp,
      isTs: true,
    },
    {
      metric: t('bot.profit.firstTrade'),
      value: profit.value.first_trade_timestamp,
      isTs: true,
    },
    {
      metric: t('bot.profit.latestTrade'),
      value: profit.value.latest_trade_timestamp,
      isTs: true,
    },
    {
      metric: t('bot.profit.winLoss'),
      value: `${profit.value.winning_trades ?? 0} / ${profit.value.losing_trades ?? 0}`,
    },
    {
      metric: t('bot.profit.winrate'),
      value: `${profit.value.winrate ? formatPercent(profit.value.winrate) : t('bot.na')}`,
    },
    {
      metric: t('bot.profit.expectancy'),
      value: `${formatNumber(profit.value.expectancy, 2)} (${formatNumber(profit.value.expectancy_ratio, 2)})`,
    },
    {
      metric: 'CAGR',
      value: `${formatPercent(profit.value.cagr, 2)}`,
    },
    {
      metric: 'Calmar',
      value: `${formatNumber(profit.value.calmar, 2)}`,
    },
    {
      metric: 'Sharpe',
      value: `${formatNumber(profit.value.sharpe, 2)}`,
    },
    {
      metric: 'Sortino',
      value: `${formatNumber(profit.value.sortino, 2)}`,
    },
    {
      metric: 'SQN',
      value: `${formatNumber(profit.value.sqn, 2)}`,
    },
    {
      metric: t('bot.profit.avgDuration'),
      value: `${profit.value.avg_duration ?? t('bot.na')}`,
    },
    {
      metric: t('bot.profit.bestPerforming'),
      value: profit.value.best_pair
        ? `${profit.value.best_pair}: ${formatPercent(profit.value.best_pair_profit_ratio, 2)}`
        : t('bot.na'),
    },
    {
      metric: t('bot.profit.tradingVolume'),
      value: `${formatPriceCurrency(
        profit.value.trading_volume ?? 0,
        props.stakeCurrency,
        props.stakeCurrencyDecimals,
      )}`,
    },
    {
      metric: t('bot.profit.profitFactor'),
      value: `${formatNumber(profit.value.profit_factor, 2)}`,
    },
    {
      metric: t('bot.profit.maxDrawdown'),
      value: `${profit.value.max_drawdown ? formatPercent(profit.value.max_drawdown, 2) : t('bot.na')} (${
        profit.value.max_drawdown_abs
          ? formatPriceCurrency(
              profit.value.max_drawdown_abs,
              props.stakeCurrency,
              props.stakeCurrencyDecimals,
            )
          : t('bot.na')
      }) ${
        profit.value.max_drawdown_start_timestamp && profit.value.max_drawdown_end_timestamp
          ? t('bot.profit.fromTo', {
              start: timestampms(profit.value.max_drawdown_start_timestamp),
              end: timestampms(profit.value.max_drawdown_end_timestamp),
            })
          : ''
      }`,
    },
    {
      metric: t('bot.profit.currentDrawdown'),
      value: `${profit.value.current_drawdown ? formatPercent(profit.value.current_drawdown, 2) : t('bot.na')} (${
        profit.value.current_drawdown_abs
          ? formatPriceCurrency(
              profit.value.current_drawdown_abs,
              props.stakeCurrency,
              props.stakeCurrencyDecimals,
            )
          : t('bot.na')
      }) ${
        profit.value.current_drawdown_start_timestamp
          ? t('bot.profit.since', {
              start: timestampms(profit.value.current_drawdown_start_timestamp),
            })
          : ''
      }`,
    },
  ];
});

const selectedOption = ref('all');
const options = computed(() => [
  { value: 'all', text: t('common.all') },
  { value: 'long', text: t('bot.profit.optLong') },
  { value: 'short', text: t('bot.profit.optShort') },
]);
</script>

<template>
  <div>
    <div v-if="profitAll?.long && profitAll?.short" class="flex justify-between items-center">
      <span>{{ t('bot.profit.profitsFor') }}</span>
      <USegmentedControl
        v-model="selectedOption"
        :items="options"
        label-key="text"
        value-key="value"
      ></USegmentedControl>
      <span>{{ t('bot.profit.trades') }}</span>
    </div>

    <UTable
      class="text-start"
      :data="profitItems"
      :columns="[
        { accessorKey: 'metric', header: t('bot.profit.colMetric') },
        { accessorKey: 'value', header: t('bot.profit.colValue') },
      ]"
      :ui="{
        td: 'whitespace-normal',
      }"
    >
      <template #value-cell="{ row }">
        <DateTimeTZ v-if="row.original.isTs" :date="row.original.value" show-timezone />
        <template v-else>
          {{ row.original.value }}
        </template>
      </template>
    </UTable>
  </div>
</template>
