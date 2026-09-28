<script setup lang="ts">
import { getPaginationRowModel } from '@tanstack/vue-table';
import type { TableColumn, TableRow } from '@nuxt/ui';
import type { MultiDeletePayload, MultiForceExitPayload, Trade } from '@/types';

import { useRouter } from 'vue-router';

const props = withDefaults(
  defineProps<{
    trades: Trade[];
    title?: string;
    stakeCurrency?: string;
    activeTrades?: boolean;
    showFilter?: boolean;
    multiBotView?: boolean;
    emptyText?: string;
  }>(),
  {
    title: 'Trades',
    stakeCurrency: '',
    activeTrades: false,
    showFilter: false,
    multiBotView: false,
  },
);

const { t: tr } = useI18n();
const botStore = useBotStore();
const router = useRouter();
const settingsStore = useSettingsStore();
const tradesTable = useTemplateRef('tradesTable');
const filterText = ref('');
const perPage = props.activeTrades ? 200 : 15;
const pagination = ref({ pageIndex: 0, pageSize: perPage });
const { confirm } = useConfirmBox();
const { forceEntryDialog, forceExitDialog } = useForceTrade();

function formatPriceWithDecimals(price: number) {
  return formatPrice(price, botStore.activeBot.stakeCurrencyDecimals);
}

const tableFields = computed(() => [
  ...(props.multiBotView ? [{ field: 'botName', header: tr('tradeList.col.bot') }] : []),
  { field: 'trade_id', header: tr('tradeList.col.id') },
  { field: 'pair', header: tr('tradeList.col.pair') },
  { field: 'amount', header: tr('tradeList.col.amount') },
  props.activeTrades
    ? { field: 'stake_amount', header: tr('tradeList.col.stakeAmount') }
    : { field: 'max_stake_amount', header: tr('tradeList.col.totalStakeAmount') },
  {
    field: 'open_rate',
    header: tr('tradeList.col.openRate'),
  },
  {
    field: props.activeTrades ? 'current_rate' : 'close_rate',
    header: props.activeTrades ? tr('tradeList.col.currentRate') : tr('tradeList.col.closeRate'),
  },
  {
    field: 'profit',
    header: props.activeTrades
      ? tr('tradeList.col.currentProfitPct')
      : tr('tradeList.col.profitPct'),
  },
  { field: 'open_timestamp', header: tr('tradeList.col.openDate') },
  ...(props.activeTrades
    ? [{ field: 'actions', header: '' }]
    : [
        { field: 'close_timestamp', header: tr('tradeList.col.closeDate') },
        { field: 'exit_reason', header: tr('tradeList.col.exitReason') },
      ]),
]);

/** Numeric columns are right aligned with tabular numerals. */
const numericFields = [
  'amount',
  'stake_amount',
  'max_stake_amount',
  'open_rate',
  'current_rate',
  'close_rate',
  'profit',
];
const tableColumns = computed<TableColumn<Trade>[]>(() =>
  tableFields.value.map((f) => ({
    accessorKey: f.field,
    header: f.header,
    meta: numericFields.includes(f.field)
      ? { class: { th: 'text-end', td: 'nova-num text-end' } }
      : f.field.endsWith('timestamp')
        ? { class: { td: 'nova-num' } }
        : undefined,
  })),
);

/** Leverage suffix, only when the trade actually has one. */
function leverageSuffix(trade: Trade) {
  return trade.trading_mode !== 'spot' && trade.leverage ? ` (${trade.leverage}x)` : '';
}

const filteredTrades = computed(() => {
  if (!filterText.value) return props.trades;
  const text = filterText.value.toLowerCase();
  return props.trades.filter(
    (t) =>
      t.pair.toLowerCase().includes(text) ||
      t.exit_reason?.toLowerCase().includes(text) ||
      t.enter_tag?.toLowerCase().includes(text) ||
      (props.multiBotView ? t.botName?.toLowerCase().includes(text) : false),
  );
});

async function forceExitHandler(item: Trade, ordertype: string | undefined = undefined) {
  const message = ordertype
    ? tr('tradeList.confirm.forceExitMsgType', {
        id: String(item.trade_id),
        pair: item.pair,
        type: ordertype,
      })
    : tr('tradeList.confirm.forceExitMsg', { id: String(item.trade_id), pair: item.pair });
  if (
    settingsStore.confirmDialog !== true ||
    (await confirm({
      title: tr('tradeList.confirm.forceExitTitle'),
      description: tr('tradeList.confirm.cannotUndo'),
      message,
      confirmText: tr('common.confirm'),
    }))
  ) {
    const payload: MultiForceExitPayload = {
      tradeid: String(item.trade_id),
      botId: item.botId,
    };
    if (ordertype) {
      payload.ordertype = ordertype;
    }
    botStore
      .forceSellMulti(payload)
      .then((xxx) => console.log(xxx))
      .catch((error) => console.log(error.response));
  }
}

async function removeTradeHandler(item: Trade) {
  if (
    await confirm({
      title: tr('tradeList.confirm.deleteTitle'),
      description: tr('tradeList.confirm.cannotUndo'),
      message: tr('tradeList.confirm.deleteMsg', { id: String(item.trade_id), pair: item.pair }),
      confirmText: tr('common.confirm'),
    })
  ) {
    const payload: MultiDeletePayload = {
      tradeid: String(item.trade_id),
      botId: item.botId,
    };
    botStore.deleteTradeMulti(payload).catch((error) => console.log(error.response));
  }
}

function forceExitPartialHandler(item: Trade) {
  forceExitDialog({
    trade: item,
    stakeCurrencyDecimals: botStore.activeBot.botState.stake_currency_decimals ?? 3,
  });
}

async function cancelOpenOrderHandler(item: Trade) {
  if (
    await confirm({
      title: tr('tradeList.confirm.cancelOrderTitle'),
      description: tr('tradeList.confirm.cannotUndo'),
      message: tr('tradeList.confirm.cancelOrderMsg', {
        id: String(item.trade_id),
        pair: item.pair,
      }),
      confirmText: tr('common.confirm'),
    })
  ) {
    const payload: MultiDeletePayload = {
      tradeid: String(item.trade_id),
      botId: item.botId,
    };
    botStore.cancelOpenOrderMulti(payload).catch((error) => console.log(error.response));
  }
}

function reloadTradeHandler(item: Trade) {
  botStore.reloadTradeMulti({ tradeid: String(item.trade_id), botId: item.botId });
}

function handleForceEntry(item: Trade) {
  forceEntryDialog({
    pair: item.pair,
    positionIncrease: true,
  });
}

const onRowClicked = (item: Trade) => {
  if (props.multiBotView && botStore.selectedBot !== item.botId) {
    // Multibotview - on click switch to the bot trade view
    botStore.selectBot(item.botId);
  }
  if (item && item.trade_id !== botStore.activeBot.detailTradeId) {
    botStore.activeBot.setDetailTrade(item);
    if (props.multiBotView) {
      router.push('/trade');
    }
  } else {
    botStore.activeBot.setDetailTrade(null);
  }
};

function onRowSelect(_e: Event, row: TableRow<Trade>) {
  onRowClicked(row.original);
}

const rowSelection = computed({
  get() {
    const selectedTradeIndex = filteredTrades.value.findIndex(
      (t) => String(t.trade_id) === String(botStore.activeBot.detailTradeId),
    );
    if (selectedTradeIndex === -1) return {};
    return { [String(selectedTradeIndex)]: true };
  },
  set() {
    // noop, selection is controlled by activeBot.detailTradeId
  },
});
</script>

<template>
  <div class="flex h-full w-full flex-col gap-3 overflow-auto text-start">
    <div v-if="showFilter" class="flex justify-end">
      <UInput
        v-model="filterText"
        icon="i-mdi-magnify"
        :placeholder="tr('tradeList.list.filterPlaceholder')"
        :aria-label="tr('tradeList.list.filterAria')"
        class="w-full sm:w-64"
      />
    </div>
    <UTable
      ref="tradesTable"
      v-model:pagination="pagination"
      :pagination-options="{ getPaginationRowModel: getPaginationRowModel() }"
      :data="filteredTrades"
      :columns="tableColumns"
      v-model:row-selection="rowSelection"
      :ui="{
        root: 'overflow-x-auto',
        th: 'px-3 py-2 text-xs font-medium whitespace-nowrap text-muted text-start',
        td: 'px-3 py-2 text-sm whitespace-nowrap text-default',
        tr: 'cursor-pointer transition-colors duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] hover:bg-accented/40 data-[selected=true]:bg-brand-400/10',
        separator: 'bg-default/50',
      }"
      @select="onRowSelect"
    >
      <template #empty>
        <div class="flex flex-col items-center gap-3 py-6">
          <span class="flex size-10 items-center justify-center rounded-full bg-accented">
            <UIcon name="i-mdi-format-list-bulleted" class="size-5 text-muted" />
          </span>
          <span class="text-sm text-muted">{{ emptyText ?? tr('tradeList.list.empty') }}</span>
        </div>
      </template>
      <template #trade_id-cell="{ row }">
        {{ row.original.trade_id }}
        {{
          botStore.activeBot.botFeatures.futures && row.original.trading_mode !== 'spot'
            ? (row.original.trade_id ? '| ' : '') +
              (row.original.is_short ? tr('tradeList.short') : tr('tradeList.long'))
            : ''
        }}
      </template>
      <template #pair-cell="{ row }">
        {{
          `${row.original.pair}${row.original.open_order_id || row.original.has_open_orders ? '*' : ''}`
        }}
      </template>
      <template #actions-cell="{ row }">
        <TradeActionsPopover
          :id="row.original.trade_id ?? row.index"
          :enable-force-entry="botStore.activeBot.botState.force_entry_enable"
          :trade="row.original"
          :bot-features="botStore.activeBot.botFeatures"
          @delete-trade="removeTradeHandler(row.original)"
          @force-exit="forceExitHandler"
          @force-exit-partial="forceExitPartialHandler"
          @cancel-open-order="cancelOpenOrderHandler"
          @reload-trade="reloadTradeHandler"
          @force-entry="handleForceEntry"
        />
      </template>
      <template #stake_amount-cell="{ row }">
        {{ formatPriceWithDecimals(row.original.stake_amount) }}{{ leverageSuffix(row.original) }}
      </template>
      <template #max_stake_amount-cell="{ row }">
        {{ formatPriceWithDecimals(row.original.max_stake_amount || row.original.stake_amount || 0)
        }}{{ leverageSuffix(row.original) }}
      </template>
      <template #open_rate-cell="{ row }">{{ formatPrice(row.original.open_rate) }}</template>
      <template #current_rate-cell="{ row }">{{
        formatPrice(row.original.current_rate ?? null)
      }}</template>
      <template #close_rate-cell="{ row }">{{
        formatPrice(row.original.close_rate ?? null)
      }}</template>
      <template #amount-cell="{ row }">{{ formatPrice(row.original.amount) }}</template>
      <template #profit-cell="{ row }"><TradeProfit :trade="row.original" /></template>
      <template #open_timestamp-cell="{ row }"
        ><DateTimeTZ :date="row.original.open_timestamp"
      /></template>
      <template #close_timestamp-cell="{ row }"
        ><DateTimeTZ :date="row.original.close_timestamp ?? 0"
      /></template>
      <template #exit_reason-cell="{ row }">{{ row.original.exit_reason }}</template>
      <template #botName-cell="{ row }">{{ row.original.botName }}</template>
    </UTable>

    <div v-if="!activeTrades" class="flex justify-end">
      <UPagination
        :page="(tradesTable?.tableApi?.getState().pagination.pageIndex || 0) + 1"
        :items-per-page="tradesTable?.tableApi?.getState().pagination.pageSize"
        :total="tradesTable?.tableApi?.getFilteredRowModel().rows.length ?? 0"
        @update:page="(p) => tradesTable?.tableApi?.setPageIndex(p - 1)"
      />
    </div>
  </div>
</template>
