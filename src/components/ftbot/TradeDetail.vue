<script setup lang="ts">
import type { Trade } from '@/types';
import { I18nT } from 'vue-i18n';

const { t } = useI18n();

const colorStore = useColorStore();

defineProps<{
  trade: Trade;
  stakeCurrency: string;
}>();

const { showTradeCustomData } = useTradeCustomData();
</script>

<template>
  <div class="text-start grid md:grid-cols-[repeat(auto-fit,minmax(500px,1fr))] gap-4 px-2">
    <div class="">
      <div class="mb-2 flex items-center justify-between gap-2">
        <h5 class="block w-full text-base font-semibold text-highlighted">
          {{ t('tradeList.detail.general') }}
        </h5>
        <UButton
          size="sm"
          variant="outline"
          color="neutral"
          @click="showTradeCustomData({ tradeId: trade.trade_id })"
          :label="t('tradeList.detail.showCustomData')"
          icon="i-mdi-database-search"
        />
      </div>
      <ValuePair :description="t('tradeList.detail.tradeId')">{{ trade.trade_id }}</ValuePair>
      <ValuePair :description="t('tradeList.detail.pair')">{{ trade.pair }}</ValuePair>

      <ValuePair :description="t('tradeList.detail.openDate')">{{
        timestampms(trade.open_timestamp)
      }}</ValuePair>
      <ValuePair v-if="trade.enter_tag" :description="t('tradeList.detail.entryTag')">{{
        trade.enter_tag
      }}</ValuePair>
      <ValuePair v-if="trade.is_open" :description="t('tradeList.detail.stake')">
        {{ formatPriceCurrency(trade.stake_amount, stakeCurrency) }}
        <template v-if="trade.trading_mode !== 'spot'">
          ({{ trade.leverage }}x)
          <span :title="t('tradeList.detail.positionValue')" class="text-muted">{{
            formatPriceCurrency(trade.amount * trade.open_rate, stakeCurrency)
          }}</span>
        </template>
      </ValuePair>
      <ValuePair v-if="!trade.is_open" :description="t('tradeList.detail.totalStake')">
        {{ formatPriceCurrency(trade.max_stake_amount ?? trade.stake_amount, stakeCurrency) }}
        {{ trade.trading_mode !== 'spot' ? `(${trade.leverage}x)` : '' }}
      </ValuePair>
      <ValuePair :description="t('tradeList.detail.amount')">{{
        formatPrice(trade.amount)
      }}</ValuePair>
      <ValuePair :description="t('tradeList.detail.openRate')">{{
        formatPrice(trade.open_rate)
      }}</ValuePair>
      <ValuePair
        v-if="trade.is_open && trade.current_rate"
        :description="t('tradeList.detail.currentRate')"
      >
        {{ formatPrice(trade.current_rate) }}
        <span :title="t('tradeList.detail.currentValueHint')" class="text-muted">
          ({{ formatPriceCurrency(trade.stake_amount + (trade.profit_abs ?? 0), stakeCurrency) }})
        </span>
      </ValuePair>
      <ValuePair
        v-if="!trade.is_open && trade.close_rate"
        :description="t('tradeList.detail.closeRate')"
        >{{ formatPrice(trade.close_rate) }}</ValuePair
      >

      <ValuePair v-if="trade.close_timestamp" :description="t('tradeList.detail.closeDate')">{{
        timestampms(trade.close_timestamp)
      }}</ValuePair>
      <ValuePair
        v-if="trade.is_open && trade.realized_profit && !trade.total_profit_abs"
        :description="t('tradeList.detail.realizedProfit')"
      >
        <TradeProfit :trade="trade" mode="realized" />
      </ValuePair>
      <ValuePair
        v-if="trade.is_open && trade.total_profit_abs"
        :description="t('tradeList.detail.totalProfit')"
      >
        <TradeProfit :trade="trade" mode="total" />
      </ValuePair>
      <ValuePair
        v-if="trade.profit_ratio && trade.profit_abs"
        :description="
          trade.is_open ? t('tradeList.detail.currentProfit') : t('tradeList.detail.closeProfit')
        "
      >
        <TradeProfit :trade="trade" />
      </ValuePair>
      <BaseCollapsible :title="t('tradeList.detail.details')" class="px-2 pb-2">
        <ValuePair v-if="trade.min_rate" :description="t('tradeList.detail.minRate')">{{
          formatPrice(trade.min_rate)
        }}</ValuePair>
        <ValuePair v-if="trade.max_rate" :description="t('tradeList.detail.maxRate')">{{
          formatPrice(trade.max_rate)
        }}</ValuePair>
        <ValuePair :description="t('tradeList.detail.openFees')">
          {{ trade.fee_open_cost }} {{ trade.quote_currency }}
          <span v-if="trade.quote_currency !== trade.fee_open_currency">
            {{ t('tradeList.detail.inCurrency', { currency: trade.fee_open_currency ?? '' }) }}
          </span>
          ({{ formatPercent(trade.fee_open) }})
        </ValuePair>
        <ValuePair
          v-if="trade.fee_close_cost && trade.fee_close"
          :description="t('tradeList.detail.feesClose')"
        >
          {{ trade.fee_close_cost }} {{ trade.fee_close_currency }} ({{
            formatPercent(trade.fee_close)
          }})
        </ValuePair>
      </BaseCollapsible>
    </div>
    <div class="mt-2 lg:mt-0">
      <h5 class="mt-4 mb-2 block w-full text-base font-semibold text-highlighted">
        {{ t('tradeList.detail.stoplossTitle') }}
      </h5>
      <ValuePair :description="t('tradeList.detail.stoploss')">
        {{ formatPercent(trade.stop_loss_ratio) }} |
        {{ formatPrice(trade.stop_loss_abs) }}
      </ValuePair>
      <ValuePair
        :description="t('tradeList.detail.atRisk')"
        :help="t('tradeList.detail.atRiskHelp')"
      >
        {{
          formatPriceCurrency(trade.stake_amount * Math.abs(trade.stop_loss_ratio), stakeCurrency)
        }}
      </ValuePair>
      <ValuePair
        v-if="trade.is_open && trade.stoploss_current_dist_ratio && trade.stoploss_current_dist"
        :description="t('tradeList.detail.currentStoplossDist')"
      >
        {{ formatPercent(trade.stoploss_current_dist_ratio) }} |
        {{ formatPrice(trade.stoploss_current_dist) }}
      </ValuePair>
      <ValuePair
        v-if="trade.initial_stop_loss_pct && trade.initial_stop_loss_abs"
        :description="t('tradeList.detail.initialStoploss')"
      >
        {{ formatPercent(trade.initial_stop_loss_pct / 100) }} |
        {{ formatPrice(trade.initial_stop_loss_abs) }}
      </ValuePair>
      <ValuePair
        v-if="trade.stoploss_last_update_timestamp"
        :description="t('tradeList.detail.stoplossUpdated')"
      >
        {{ timestampms(trade.stoploss_last_update_timestamp) }}
      </ValuePair>
      <div v-if="trade.trading_mode !== undefined && trade.trading_mode !== 'spot'">
        <h5 class="mt-4 mb-2 block w-full text-base font-semibold text-highlighted">
          {{ t('tradeList.detail.futures') }}
        </h5>
        <ValuePair :description="t('tradeList.detail.direction')">
          {{ trade.is_short ? t('tradeList.detail.short') : t('tradeList.detail.long') }} -
          {{ trade.leverage }}x
        </ValuePair>
        <ValuePair
          v-if="trade.funding_fees !== undefined"
          :description="t('tradeList.detail.fundingFees')"
          :help="t('tradeList.detail.fundingFeesHelp')"
        >
          {{ formatDecimal(trade.funding_fees) }}
        </ValuePair>
        <ValuePair
          v-if="trade.interest_rate !== undefined"
          :description="t('tradeList.detail.interestRate')"
        >
          {{ formatDecimal(trade.interest_rate) }}
        </ValuePair>
        <ValuePair
          v-if="trade.liquidation_price !== undefined"
          :description="t('tradeList.detail.liquidationPrice')"
        >
          {{ formatPrice(trade.liquidation_price) }}
        </ValuePair>
      </div>
      <BaseCollapsible
        v-if="trade.orders"
        :title="`${t('tradeList.detail.orders')} ${trade.orders.length > 1 ? `[${trade.orders.length}]` : ''}`"
        class="px-2 pb-2"
      >
        <div
          v-for="(order, key) in trade.orders"
          :key="key"
          class="flex items-center gap-1 2"
          :title="
            t('tradeList.detail.orderTitle', {
              side: order.ft_order_side,
              type: order.order_type,
              amount: formatPriceCurrency(order.amount, trade.base_currency ?? ''),
              price: formatPriceCurrency(order.safe_price, trade.quote_currency ?? ''),
              filled: formatPrice(order.filled),
            })
          "
        >
          (#{{ key + 1 }})
          <i-mdi-triangle
            v-if="order.ft_order_side === 'buy'"
            class="me-1"
            :style="{
              color: colorStore.colorUp,
            }"
            style="font-size: 0.6rem"
          />
          <i-mdi-triangle-down
            v-else
            class="me-1"
            :style="{ color: colorStore.colorDown }"
            style="font-size: 0.6rem"
          />
          <DateTimeTZ v-if="order.order_timestamp" :date="order.order_timestamp" show-timezone />
          <b
            class="ms-1"
            :style="{
              color: order.ft_order_side === 'buy' ? colorStore.colorUp : colorStore.colorDown,
            }"
            >{{ order.ft_order_side }}</b
          >
          <I18nT keypath="tradeList.detail.orderFor" tag="span" scope="global">
            <template #price>
              <b>{{ formatPrice(order.safe_price) }}</b>
            </template>
          </I18nT>
          |
          <span
            v-if="order.remaining && order.remaining !== 0"
            :title="t('tradeList.detail.remaining')"
            >{{ formatPrice(order.remaining, 8) }} /
          </span>
          <span :title="t('tradeList.detail.filled')">{{ formatPrice(order.filled ?? 0, 8) }}</span>
          <template v-if="order.ft_order_tag"> | {{ order.ft_order_tag ?? '' }}</template>
        </div>
      </BaseCollapsible>
    </div>
  </div>
</template>
