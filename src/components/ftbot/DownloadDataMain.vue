<script setup lang="ts">
import type { DownloadDataPayload, ExchangeSelection } from '@/types';
import { MarginMode, TradingMode } from '@/types';
import type { SelectMenuItem } from '@nuxt/ui';

const { t } = useI18n();
const botStore = useBotStore();
const pairlistStore = usePairlistConfigStore();
const pairs = ref<string[]>(['BTC/USDT', 'ETH/USDT', '']);
const timeframes = ref<string[]>(['5m', '1h']);

const timeSelection = ref({
  useCustomTimerange: false,
  timerange: '',
  days: 30,
});

const { pairTemplates } = usePairTemplates();

const exchange = ref<{
  customExchange: boolean;
  selectedExchange: ExchangeSelection;
}>({
  customExchange: false,
  selectedExchange: {
    exchange: 'binance',
    trade_mode: {
      margin_mode: MarginMode.NONE,
      trading_mode: TradingMode.SPOT,
    },
  },
});

const advancedOptions = ref({
  erase: false,
  prepend_data: false,
  downloadTrades: false,
  candleTypes: [] as string[],
});

// State to track the collapse status
const isAdvancedOpen = ref(false);
const candleTypes: SelectMenuItem[] = [
  { label: 'Spot', value: 'spot' },
  { label: 'Futures', value: 'futures' },
  { label: 'Funding Rate', value: 'funding_rate' },
  { label: 'Mark', value: 'mark' },
  { label: 'Index', value: 'index' },
  { label: 'Premium Index', value: 'premiumIndex' },
];

function addPairs(_pairs: string[]) {
  pairs.value.push(..._pairs);
}

function replacePairs(_pairs: string[]) {
  pairs.value = [..._pairs];
}

async function startDownload() {
  const payload: DownloadDataPayload = {
    pairs: pairs.value.filter((pair) => pair !== ''),
    timeframes: timeframes.value.filter((tf) => tf !== ''),
  };

  // Add either timerange or days to the payload
  if (timeSelection.value.useCustomTimerange && timeSelection.value.timerange) {
    payload.timerange = timeSelection.value.timerange;
  } else {
    payload.days = timeSelection.value.days;
  }

  // Include advanced options only if the section is open
  if (isAdvancedOpen.value) {
    payload.erase = advancedOptions.value.erase;
    payload.download_trades = advancedOptions.value.downloadTrades;

    if (exchange.value.customExchange) {
      payload.exchange = exchange.value.selectedExchange.exchange;
      payload.trading_mode = exchange.value.selectedExchange.trade_mode.trading_mode;
      payload.margin_mode = exchange.value.selectedExchange.trade_mode.margin_mode;
    }
    if (
      botStore.activeBot.botFeatures.downloadDataCandleTypes &&
      advancedOptions.value.candleTypes.length > 0
    ) {
      payload.candle_types = advancedOptions.value.candleTypes;
    }
    if (botStore.activeBot.botFeatures.downloadDataPrepend && advancedOptions.value.prepend_data) {
      payload.prepend_data = true;
    }
  }

  await botStore.activeBot.startDataDownload(payload);
}
</script>

<template>
  <div class="flex w-full min-w-0 flex-col gap-6 text-start">
    <BackgroundJobTracking />
    <NovaPanel :title="t('download.main.whatToDownload')">
      <div class="flex mb-3 gap-3 flex-col">
        <div class="flex flex-col gap-3">
          <div class="flex flex-col lg:flex-row gap-3">
            <!-- Pairs section - keeping template buttons next to input -->
            <div class="flex-fill">
              <div class="flex flex-col gap-2">
                <div class="flex justify-between">
                  <h4 class="text-start text-base font-semibold text-highlighted">
                    {{ t('download.main.pairs') }}
                  </h4>
                  <h5 class="text-start text-base font-semibold text-highlighted">
                    {{ t('download.main.pairsFromTemplate') }}
                  </h5>
                </div>
                <div class="flex gap-2">
                  <BaseStringList
                    v-model="pairs"
                    :placeholder="t('download.main.pair')"
                    class="grow"
                  />
                  <div class="flex flex-col gap-1">
                    <div class="flex flex-col gap-1">
                      <UButton
                        v-for="pt in pairTemplates"
                        :key="pt.idx"
                        color="neutral"
                        :title="pt.pairs.reduce((acc, p) => `${acc}${p}\n`, '')"
                        @click="addPairs(pt.pairs)"
                      >
                        {{ pt.description }}
                      </UButton>
                    </div>
                    <USeparator />
                    <UButton
                      :disabled="pairlistStore.whitelist.length === 0"
                      :title="t('download.main.usePairlistHint')"
                      color="neutral"
                      @click="replacePairs(pairlistStore.whitelist)"
                    >
                      {{ t('download.main.usePairlist') }}
                    </UButton>
                  </div>
                </div>
              </div>
            </div>

            <!-- Timeframes section -->
            <div class="flex-fill">
              <div class="flex flex-col gap-2">
                <h4 class="text-start text-base font-semibold text-highlighted">
                  {{ t('download.main.timeframes') }}
                </h4>
                <BaseStringList v-model="timeframes" :placeholder="t('download.main.timeframe')" />
              </div>
            </div>
          </div>

          <!-- Time selection section -->
          <div class="nova-tile p-4">
            <div class="flex flex-col gap-2">
              <div class="flex justify-between items-center">
                <h4 class="text-start mb-0 text-base font-semibold text-highlighted">
                  {{ t('download.main.timeRange') }}
                </h4>
                <BaseCheckbox v-model="timeSelection.useCustomTimerange" class="mb-0" switch>
                  {{ t('download.main.customTimeRange') }}
                </BaseCheckbox>
              </div>

              <div v-if="timeSelection.useCustomTimerange">
                <TimeRangeSelect
                  v-model="timeSelection.timerange"
                  :can-use-time="botStore.activeBot.botFeatures.timerangeWithTime"
                />
              </div>
              <div v-else class="flex items-center gap-2">
                <label class="text-sm text-muted">{{ t('download.main.days') }}</label>
                <UInputNumber
                  v-model="timeSelection.days"
                  :aria-label="t('download.main.days')"
                  :min="1"
                  :step="1"
                />
              </div>
            </div>
          </div>
          <!-- Advanced options section -->
          <BaseCollapsible v-model:open="isAdvancedOpen" :title="t('download.main.advanced')">
            <UAlert color="info" class="my-2 py-2" :description="t('download.main.advancedHint')" />
            <div class="nova-tile mb-2 flex flex-col gap-2 p-4 text-start">
              <BaseCheckbox v-model="advancedOptions.erase" class="mb-2">{{
                t('download.main.erase')
              }}</BaseCheckbox>
              <BaseCheckbox
                v-model="advancedOptions.prepend_data"
                class="mb-2"
                v-if="botStore.activeBot.botFeatures.downloadDataPrepend"
                >{{ t('download.main.prepend') }}</BaseCheckbox
              >
              <BaseCheckbox v-model="advancedOptions.downloadTrades" class="mb-2">
                {{ t('download.main.downloadTrades') }}
              </BaseCheckbox>
              <div class="grid grid-cols md:grid-cols-2 items-center gap-2">
                <USelectMenu
                  multiple
                  v-if="botStore.activeBot.botFeatures.downloadDataCandleTypes"
                  v-model="advancedOptions.candleTypes"
                  :items="candleTypes"
                  :placeholder="t('download.main.candleTypes')"
                  value-key="value"
                />
                <p class="text-sm text-pretty text-muted">
                  {{ t('download.main.candleTypesHint') }}
                </p>
              </div>
            </div>
            <div class="nova-tile mb-2 flex flex-col gap-2 p-4 text-start">
              <UCollapsible v-model:open="exchange.customExchange">
                <BaseCheckbox v-model="exchange.customExchange" class="mb-2">
                  {{ t('download.main.customExchange') }}
                </BaseCheckbox>
                <template #content>
                  <ExchangeSelect
                    v-show="exchange.customExchange"
                    v-model="exchange.selectedExchange"
                  />
                </template>
              </UCollapsible>
            </div>
          </BaseCollapsible>

          <div>
            <UButton
              color="primary"
              variant="solid"
              icon="i-mdi-download"
              class="px-4 font-semibold"
              @click="startDownload"
              >{{ t('download.main.start') }}</UButton
            >
          </div>
        </div>
      </div>
    </NovaPanel>
  </div>
</template>
