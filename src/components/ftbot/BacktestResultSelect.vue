<script setup lang="ts">
import type { BacktestResultInMemory, BacktestResultUpdate } from '@/types';

withDefaults(
  defineProps<{
    backtestHistory: Record<string, BacktestResultInMemory>;
    selectedBacktestResultKey?: string;
    canUseModify?: boolean;
  }>(),
  {
    selectedBacktestResultKey: '',
    canUseModify: false,
  },
);

const { t } = useI18n();

const emit = defineEmits<{
  selectionChange: [value: string];
  removeResult: [value: string];
  updateResult: [value: BacktestResultUpdate];
}>();

function confirmInput(run_id: string, result: BacktestResultInMemory) {
  result.metadata.editing = !result.metadata.editing;
  if (result.metadata.filename) {
    emit('updateResult', {
      run_id: run_id,
      notes: result.metadata.notes ?? '',
      filename: result.metadata.filename,
      strategy: result.metadata.strategyName,
    });
  }
}
</script>

<template>
  <section class="flex flex-col gap-3 text-start" aria-labelledby="bt-loaded-results-title">
    <h2 id="bt-loaded-results-title" class="px-1 text-base font-semibold text-highlighted">
      {{ t('backtest.loaded.title') }}
    </h2>
    <div
      v-if="Object.keys(backtestHistory).length === 0"
      class="nova-tile flex flex-col items-center gap-3 p-4 text-center"
    >
      <span class="flex size-10 items-center justify-center rounded-full bg-accented">
        <UIcon name="i-mdi-flask-empty-outline" class="size-5 text-muted" />
      </span>
      <p class="text-sm text-pretty text-muted">
        {{ t('backtest.loaded.empty') }}
      </p>
    </div>
    <ul v-else class="flex flex-col gap-1">
      <li
        v-for="[key, result] in Object.entries(backtestHistory)"
        :key="key"
        tabindex="0"
        :aria-current="key === selectedBacktestResultKey ? 'true' : undefined"
        class="flex cursor-pointer items-center justify-between gap-2 rounded-xl px-3 py-2 transition duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-400/60 active:scale-[0.98]"
        :class="
          key === selectedBacktestResultKey
            ? 'bg-brand-400/10 ring-1 ring-brand-400/40'
            : 'hover:bg-accented/60'
        "
        @click="$emit('selectionChange', key)"
        @keydown.enter.self="$emit('selectionChange', key)"
      >
        <template v-if="!result.metadata.editing">
          <BacktestResultSelectEntry :backtest-result="result" :can-use-modify="canUseModify" />
          <div class="flex shrink-0 gap-0.5">
            <UTooltip v-if="canUseModify" :text="t('backtest.loaded.editNotes')">
              <UButton
                size="sm"
                color="neutral"
                variant="ghost"
                :aria-label="t('backtest.loaded.editNotes')"
                icon="i-mdi-pencil-outline"
                @click.stop="result.metadata.editing = !result.metadata.editing"
              />
            </UTooltip>
            <UTooltip :text="t('backtest.history.unloadHint')">
              <UButton
                size="sm"
                color="neutral"
                variant="ghost"
                :aria-label="t('backtest.history.unload')"
                icon="i-mdi-close"
                @click.stop="$emit('removeResult', key)"
              />
            </UTooltip>
          </div>
        </template>
        <template v-if="result.metadata.editing">
          <UTextarea
            v-model="result.metadata.notes"
            :placeholder="t('backtest.loaded.notes')"
            size="sm"
            class="w-full"
            @click.stop
          />
          <UButton
            size="sm"
            :aria-label="t('backtest.loaded.saveNotes')"
            :title="t('backtest.loaded.saveNotes')"
            color="primary"
            variant="soft"
            icon="i-mdi-check"
            @click.stop="confirmInput(key, result)"
          />
        </template>
      </li>
    </ul>
  </section>
</template>
