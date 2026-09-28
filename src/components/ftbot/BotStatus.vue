<script setup lang="ts">
import { I18nT } from 'vue-i18n';

const { t } = useI18n();
const botStore = useBotStore();
</script>

<template>
  <div v-if="botStore.activeBot.botState" class="p-4">
    <I18nT keypath="bot.status.engine" tag="p" scope="global" class="mb-4">
      <template #version>
        <strong>{{ botStore.activeBot.version }}</strong>
      </template>
    </I18nT>
    <I18nT keypath="bot.status.runningWith" tag="p" scope="global" class="mb-4">
      <template #stake>
        <strong>
          {{ botStore.activeBot.botState.max_open_trades }}x{{
            botStore.activeBot.botState.stake_amount
          }}
          {{ botStore.activeBot.botState.stake_currency }}
        </strong>
      </template>
      <template #exchange>
        <strong class="text-nowrap"
          >{{ botStore.activeBot.botState.exchange }}
          {{ botStore.activeBot.botState.demo_trading ? t('bot.status.demo') : '' }}</strong
        >
      </template>
      <template #mode>
        <strong
          >{{ botStore.activeBot.botState.trading_mode || 'spot' }}
          {{
            botStore.activeBot.botState.trading_mode !== 'spot'
              ? (botStore.activeBot.botState.margin_mode ?? '')
              : ''
          }}</strong
        >
      </template>
      <template #strategy>
        <strong>{{ botStore.activeBot.botState.strategy }}</strong>
      </template>
    </I18nT>
    <I18nT
      v-if="'stoploss_on_exchange' in botStore.activeBot.botState"
      keypath="bot.status.stoplossOnExchange"
      tag="p"
      scope="global"
      class="mb-4"
    >
      <template #state>
        <strong>{{
          botStore.activeBot.botState.stoploss_on_exchange
            ? t('bot.status.enabled')
            : t('bot.status.disabled')
        }}</strong>
      </template>
    </I18nT>
    <I18nT keypath="bot.status.currently" tag="p" scope="global" class="mb-4">
      <template #state>
        <strong>{{ botStore.activeBot.botState.state }}</strong>
      </template>
      <template #forceEntry>
        <strong>{{
          t('bot.status.forceEntry', {
            value: String(botStore.activeBot.botState.force_entry_enable),
          })
        }}</strong>
      </template>
    </I18nT>
    <p>
      <strong>{{
        botStore.activeBot.botState.dry_run ? t('bot.status.dryRun') : t('bot.status.live')
      }}</strong>
    </p>
    <USeparator class="my-2" />
    <p class="mb-4" v-if="botStore.activeBot.profit">
      {{
        t('bot.status.avgProfit', {
          avg: formatPercent(botStore.activeBot.profit.profit_all_ratio_mean),
          sum: formatPercent(botStore.activeBot.profit.profit_all_ratio_sum),
          count: String(botStore.activeBot.profit.trade_count),
          duration: String(botStore.activeBot.profit.avg_duration),
          pair: String(botStore.activeBot.profit.best_pair),
        })
      }}
    </p>
    <p v-if="botStore.activeBot.profit?.first_trade_timestamp" class="mb-4">
      <span v-if="botStore.activeBot.profit.bot_start_timestamp" class="block">
        {{ t('bot.status.botStartDate') }}
        <strong>
          <DateTimeTZ :date="botStore.activeBot.profit.bot_start_timestamp" show-timezone />
        </strong>
      </span>
      <span class="block">
        {{ t('bot.status.firstTradeOpened') }}
        <strong>
          <DateTimeTZ :date="botStore.activeBot.profit.first_trade_timestamp" show-timezone />
        </strong>
      </span>
      <span class="block">
        {{ t('bot.status.lastTradeOpened') }}
        <strong>
          <DateTimeTZ :date="botStore.activeBot.profit.latest_trade_timestamp" show-timezone />
        </strong>
      </span>
    </p>
    <p>
      <span v-if="botStore.activeBot.profit?.profit_factor" class="block">
        {{ t('bot.status.profitFactor') }}
        {{ formatNumber(botStore.activeBot.profit?.profit_factor, 2) }}
      </span>
      <span v-if="botStore.activeBot.profit?.trading_volume" class="block mb-4">
        {{ t('bot.status.tradingVolume') }}
        {{
          formatPriceCurrency(
            botStore.activeBot.profit.trading_volume,
            botStore.activeBot.botState.stake_currency,
            botStore.activeBot.botState.stake_currency_decimals ?? 3,
          )
        }}
      </span>
    </p>
    <BaseCollapsible
      v-if="botStore.activeBot.strategy?.params"
      :title="t('bot.status.strategyParams')"
    >
      <StrategyParameters :strategy="botStore.activeBot.strategy" class="m-3" />
    </BaseCollapsible>
    <USeparator class="my-5" />
    <BotProfit
      class="mx-1"
      v-if="botStore.activeBot.profitAll"
      :profit-all="botStore.activeBot.profitAll"
      :stake-currency="botStore.activeBot.botState.stake_currency ?? 'USDT'"
      :stake-currency-decimals="botStore.activeBot.botState.stake_currency_decimals ?? 3"
    />
  </div>
</template>
