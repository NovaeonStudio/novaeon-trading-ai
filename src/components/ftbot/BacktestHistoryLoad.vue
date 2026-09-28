<script setup lang="ts">
import type { BacktestHistoryEntry } from '@/types';
import type { TableColumn } from '@nuxt/ui';
import type { TableMeta, Row } from '@tanstack/vue-table';

const { t } = useI18n();
const botStore = useBotStore();
const { confirm } = useConfirmBox();
const filterText = ref('');
const filterTextDebounced = refDebounced(filterText, 350, { maxWait: 1000 });

onMounted(() => {
  botStore.activeBot.getBacktestHistory();
});

async function deleteBacktestResult(result: BacktestHistoryEntry) {
  if (
    await confirm({
      title: t('backtest.history.deleteTitle'),
      message: t('backtest.history.deleteMessage', { file: result.filename }),
      confirmText: t('common.delete'),
    })
  ) {
    botStore.activeBot.deleteBacktestHistoryResult(result);
  }
}

const filteredList = computed(() =>
  botStore.activeBot.backtestHistoryList.filter(
    (r) =>
      r.filename.toLowerCase().includes(filterTextDebounced.value.toLowerCase()) ||
      r.strategy.toLowerCase().includes(filterTextDebounced.value.toLowerCase()),
  ),
);
const columns = computed<TableColumn<BacktestHistoryEntry>[]>(() => [
  {
    accessorKey: 'strategy',
    header: t('backtest.history.colStrategy'),
    meta: { class: { td: 'font-medium' } },
  },
  {
    accessorKey: 'timeframe',
    header: t('backtest.history.colDetails'),
    meta: { class: { td: 'nova-num' } },
  },
  {
    accessorKey: 'backtest_start_time',
    header: t('backtest.history.colRunAt'),
    meta: { class: { td: 'nova-num' } },
  },
  {
    accessorKey: 'filename',
    header: t('backtest.history.colFile'),
    meta: { class: { td: 'text-muted' } },
  },
  {
    id: 'actions',
    header: t('backtest.history.colActions'),
    meta: { class: { th: 'text-end', td: 'text-end' } },
  },
]);

/** Compact, sentence case table look shared by the backtest result tables. */
const tableUi = {
  root: 'overflow-x-auto',
  base: 'min-w-full',
  th: 'px-3 py-2 text-xs font-medium whitespace-nowrap text-muted text-start',
  td: 'px-3 py-2 text-sm whitespace-nowrap text-default',
  tr: 'cursor-pointer transition-colors duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] hover:bg-accented/40',
  separator: 'bg-default/50',
};

function isRowLoaded(row: Row<BacktestHistoryEntry>) {
  return row.original.run_id in botStore.activeBot.backtestHistory;
}

const meta: TableMeta<BacktestHistoryEntry> = {
  class: {
    tr: (row: Row<BacktestHistoryEntry>) => {
      if (isRowLoaded(row)) {
        return 'bg-brand-400/10 cursor-not-allowed';
      }
      return '';
    },
  },
};
</script>

<template>
  <NovaPanel :title="t('backtest.history.title')" :subtitle="t('backtest.history.subtitle')">
    <template #actions>
      <div class="flex w-full items-center gap-2 sm:w-auto">
        <UInput
          v-if="botStore.activeBot.backtestHistoryList.length > 0"
          id="trade-filter"
          v-model="filterText"
          type="text"
          icon="i-mdi-magnify"
          :placeholder="t('backtest.history.filterPlaceholder')"
          :aria-label="t('backtest.history.filterLabel')"
          class="w-full sm:w-64"
        />
        <UTooltip :text="t('backtest.history.reload')">
          <UButton
            :aria-label="t('backtest.history.reload')"
            variant="outline"
            color="neutral"
            icon="i-mdi-refresh"
            @click="botStore.activeBot.getBacktestHistory"
          />
        </UTooltip>
      </div>
    </template>
    <div
      v-if="botStore.activeBot.backtestHistoryList.length === 0"
      class="flex flex-col items-center gap-3 py-8 text-center"
    >
      <span class="flex size-12 items-center justify-center rounded-full bg-accented">
        <UIcon name="i-mdi-folder-open-outline" class="size-6 text-muted" />
      </span>
      <p class="max-w-sm text-sm text-pretty text-muted">
        {{ t('backtest.history.empty') }}
      </p>
    </div>
    <UTable
      v-else
      class="h-[70dvh]"
      :data="filteredList"
      :columns="columns"
      :meta="meta"
      :ui="tableUi"
      :virtualize="{ estimateSize: 38, overscan: 12 }"
      sticky
      @select="(e, row) => botStore.activeBot.getBacktestHistoryResult(row.original)"
    >
      <template #timeframe-cell="{ row }">
        <span class="font-medium text-highlighted">{{ row.original.timeframe }}</span>
        <span
          v-if="row.original.backtest_start_ts && row.original.backtest_end_ts"
          class="ms-2 text-muted"
        >
          {{ timestampToTimeRangeString(row.original.backtest_start_ts * 1000) }}-{{
            timestampToTimeRangeString(row.original.backtest_end_ts * 1000)
          }}</span
        >
      </template>
      <template #backtest_start_time-cell="{ row }">
        <DateTimeTZ :date="row.original.backtest_start_time * 1000" />
      </template>
      <template #actions-cell="{ row }">
        <div class="flex items-center justify-end gap-0.5">
          <InfoBox
            v-if="botStore.activeBot.botFeatures.backtestSetNotes"
            :class="row.original.notes ? 'opacity-100' : 'opacity-0'"
            :hint="row.original.notes ?? ''"
          ></InfoBox>
          <UTooltip
            v-if="botStore.activeBot.botFeatures.backtestDelete && !isRowLoaded(row)"
            :text="t('backtest.history.load')"
          >
            <UButton
              size="sm"
              variant="soft"
              :aria-label="t('backtest.history.load')"
              color="primary"
              icon="i-mdi-arrow-right"
              :disabled="isRowLoaded(row)"
              @click.stop="botStore.activeBot.getBacktestHistoryResult(row.original)"
            />
          </UTooltip>
          <UTooltip v-if="isRowLoaded(row)" :text="t('backtest.history.unloadHint')">
            <UButton
              :aria-label="t('backtest.history.unload')"
              icon="i-mdi-close"
              size="sm"
              variant="soft"
              color="success"
              @click.stop="botStore.activeBot.removeBacktestResultFromMemory(row.original.run_id)"
            />
          </UTooltip>
          <UTooltip
            v-if="botStore.activeBot.botFeatures.backtestDelete"
            :text="t('backtest.history.deleteFromDisk')"
          >
            <UButton
              size="sm"
              color="neutral"
              variant="ghost"
              :aria-label="t('backtest.history.deleteFromDiskLabel')"
              icon="i-mdi-trash-can-outline"
              :disabled="isRowLoaded(row)"
              @click.stop="deleteBacktestResult(row.original)"
            />
          </UTooltip>
        </div>
      </template>
    </UTable>
  </NovaPanel>
</template>
