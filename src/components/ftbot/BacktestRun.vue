<script setup lang="ts">
import type { BacktestPayload } from '@/types';

const { t } = useI18n();
const botStore = useBotStore();
const btStore = useBtStore();

function clickBacktest() {
  const btPayload: BacktestPayload = {
    strategy: btStore.strategy,
    timerange: btStore.timerange,
    enable_protections: btStore.enableProtections,
  };
  if (btStore.maxOpenTrades) {
    btPayload.max_open_trades = btStore.maxOpenTrades;
  }
  if (btStore.stakeAmountUnlimited) {
    btPayload.stake_amount = 'unlimited';
  } else {
    const stakeAmountLoc = Number(btStore.stakeAmount);
    if (stakeAmountLoc) {
      btPayload.stake_amount = stakeAmountLoc.toString();
    }
  }

  const startingCapitalLoc = Number(btStore.startingCapital);
  if (startingCapitalLoc) {
    btPayload.dry_run_wallet = startingCapitalLoc;
  }

  if (btStore.selectedTimeframe) {
    btPayload.timeframe = btStore.selectedTimeframe;
  }
  if (btStore.selectedDetailTimeframe) {
    btPayload.timeframe_detail = btStore.selectedDetailTimeframe;
  }
  if (!btStore.allowCache) {
    btPayload.backtest_cache = 'none';
  }
  if (btStore.freqAI.enabled) {
    btPayload.freqaimodel = btStore.freqAI.model;
    if (btStore.freqAI.identifier !== '') {
      btPayload.freqai = { identifier: btStore.freqAI.identifier };
    }
  }

  botStore.activeBot.startBacktest(btPayload);
}
</script>

<template>
  <div class="flex flex-col gap-6 text-start">
    <NovaPanel :title="t('backtest.run.strategy')" :subtitle="t('backtest.run.strategyHint')">
      <label for="strategy-select" class="sr-only">{{ t('backtest.run.strategy') }}</label>
      <StrategySelect v-model="btStore.strategy"></StrategySelect>
    </NovaPanel>

    <NovaPanel :title="t('backtest.run.settings')" :subtitle="t('backtest.run.settingsHint')">
      <div
        class="flex flex-col gap-6"
        :aria-busy="botStore.activeBot.backtestRunning ? 'true' : undefined"
      >
        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <UFormField :label="t('backtest.run.timeframe')">
            <TimeframeSelect
              id="timeframe-select"
              v-model="btStore.selectedTimeframe"
              class="w-full"
            />
          </UFormField>
          <UFormField
            :label="t('backtest.run.detailTimeframe')"
            :help="t('backtest.run.detailTimeframeHint')"
          >
            <TimeframeSelect
              id="timeframe-detail-select"
              v-model="btStore.selectedDetailTimeframe"
              :below-timeframe="btStore.selectedTimeframe"
              class="w-full"
            />
          </UFormField>

          <UFormField :label="t('backtest.run.maxOpenTrades')">
            <UInputNumber
              id="max-open-trades"
              v-model="btStore.maxOpenTrades"
              :placeholder="t('backtest.run.useStrategyDefault')"
              :increment="false"
              :decrement="false"
              class="nova-num w-full"
            ></UInputNumber>
          </UFormField>
          <UFormField :label="t('backtest.run.startingCapital')">
            <UInputNumber
              id="starting-capital"
              v-model="btStore.startingCapital"
              :placeholder="t('backtest.run.useConfigDefault')"
              :increment="false"
              :decrement="false"
              :step="10"
              :min="0"
              :step-snapping="false"
              :format-options="{
                maximumFractionDigits: 5,
              }"
              class="nova-num w-full"
            ></UInputNumber>
          </UFormField>

          <UFormField :label="t('backtest.run.stakeAmount')" class="sm:col-span-2">
            <div class="flex flex-col gap-3 sm:flex-row sm:items-center">
              <UInputNumber
                id="stake-amount"
                v-model="btStore.stakeAmount"
                :placeholder="t('backtest.run.useStrategyDefault')"
                class="nova-num w-full sm:max-w-xs"
                :step="10"
                :step-snapping="false"
                :format-options="{
                  maximumFractionDigits: 5,
                }"
                :min="0"
                :increment="false"
                :decrement="false"
                :disabled="btStore.stakeAmountUnlimited"
              ></UInputNumber>
              <BaseCheckbox id="stake-amount-bool" v-model="btStore.stakeAmountUnlimited">{{
                t('backtest.run.unlimitedStake')
              }}</BaseCheckbox>
            </div>
          </UFormField>
        </div>

        <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div class="nova-tile p-4">
            <BaseCheckbox id="enable-protections" v-model="btStore.enableProtections">
              {{ t('backtest.run.enableProtections') }}
              <template #hint>{{ t('backtest.run.enableProtectionsHint') }}</template>
            </BaseCheckbox>
          </div>
          <div v-if="botStore.activeBot.botFeatures.backtestFreqAI" class="nova-tile p-4">
            <BaseCheckbox id="enable-cache" v-model="btStore.allowCache">
              {{ t('backtest.run.cache') }}
              <template #hint>{{ t('backtest.run.cacheHint') }}</template>
            </BaseCheckbox>
          </div>
        </div>

        <FreqAIModelInput
          v-if="botStore.activeBot.botFeatures.backtestFreqAI"
          v-model="btStore.freqAI"
        />

        <div class="border-t border-default/50 pt-6">
          <TimeRangeSelect
            v-model="btStore.timerange"
            :can-use-time="botStore.activeBot.botFeatures.timerangeWithTime"
          ></TimeRangeSelect>
        </div>
      </div>
    </NovaPanel>

    <div class="flex flex-wrap items-center gap-2">
      <UButton
        id="start-backtest"
        color="primary"
        variant="solid"
        icon="i-mdi-play"
        class="px-4 font-semibold"
        :disabled="
          !btStore.canRunBacktest ||
          botStore.activeBot.backtestRunning ||
          !botStore.activeBot.canRunBacktest
        "
        @click="clickBacktest"
      >
        {{ t('backtest.run.start') }}
      </UButton>
      <UButton
        color="neutral"
        variant="outline"
        icon="i-mdi-refresh"
        :disabled="botStore.activeBot.backtestRunning || !botStore.activeBot.canRunBacktest"
        @click="botStore.activeBot.pollBacktest()"
      >
        {{ t('backtest.run.load') }}
      </UButton>
      <UButton
        color="neutral"
        variant="outline"
        icon="i-mdi-stop"
        :disabled="!botStore.activeBot.backtestRunning"
        @click="botStore.activeBot.stopBacktest()"
      >
        {{ t('backtest.run.stop') }}
      </UButton>
      <UButton
        color="neutral"
        variant="ghost"
        icon="i-mdi-trash-can-outline"
        :disabled="botStore.activeBot.backtestRunning || !botStore.activeBot.canRunBacktest"
        @click="botStore.activeBot.removeBacktest()"
      >
        {{ t('backtest.run.reset') }}
      </UButton>
    </div>
  </div>
</template>
