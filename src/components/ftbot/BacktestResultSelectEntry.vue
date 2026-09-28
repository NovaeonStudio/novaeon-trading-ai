<script setup lang="ts">
import type { BacktestResultInMemory } from '@/types';

withDefaults(
  defineProps<{
    backtestResult: BacktestResultInMemory;
    selectedBacktestResultKey?: string;
    canUseModify?: boolean;
  }>(),
  {
    selectedBacktestResultKey: '',
    canUseModify: false,
  },
);
const { t } = useI18n();
</script>

<template>
  <div class="flex min-w-0 flex-col text-start">
    <div class="truncate text-sm font-medium text-highlighted">
      {{ backtestResult.metadata.strategyName }}
      <span class="font-normal text-muted">· {{ backtestResult.strategy.timeframe }}</span>
    </div>
    <div class="nova-num text-xs font-normal text-muted">
      {{
        t(
          'backtest.trades',
          { count: backtestResult.strategy.total_trades },
          backtestResult.strategy.total_trades,
        )
      }}
      ·
      <span
        :class="backtestResult.strategy.profit_total >= 0 ? 'text-emerald-400' : 'text-rose-400'"
        >{{ formatPercent(backtestResult.strategy.profit_total) }}</span
      >
    </div>
    <div
      v-if="canUseModify && backtestResult.metadata.notes"
      class="mt-1 text-xs font-normal text-pretty whitespace-pre-wrap text-muted"
    >
      {{ backtestResult.metadata.notes }}
    </div>
  </div>
</template>
