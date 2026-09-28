<script setup lang="ts">
withDefaults(
  defineProps<{
    showDetails?: boolean;
  }>(),
  {
    showDetails: false,
  },
);

const strategy = defineModel<string>();

const { t } = useI18n();
const botStore = useBotStore();

const strategyCode = computed((): string => botStore.activeBot.strategy?.code ?? '');

watch(strategy, (newStrategy, oldStrategy) => {
  if (!newStrategy || newStrategy === oldStrategy) return;
  botStore.activeBot.getStrategy(newStrategy);
});

onMounted(() => {
  if (botStore.activeBot.strategyList.length === 0) {
    botStore.activeBot.getStrategyList();
  }
});
</script>

<template>
  <div class="flex flex-col gap-3">
    <div class="flex w-full gap-2">
      <USelectMenu
        id="strategy-select"
        v-model="strategy"
        :aria-label="t('strategy.select.placeholder')"
        filter
        :placeholder="t('strategy.select.placeholder')"
        class="w-full"
        :items="botStore.activeBot.strategyList"
      >
      </USelectMenu>
      <UTooltip :text="t('strategy.select.reload')">
        <UButton
          color="neutral"
          variant="outline"
          icon="i-mdi-refresh"
          :aria-label="t('strategy.select.reload')"
          @click="botStore.activeBot.getStrategyList()"
        />
      </UTooltip>
    </div>

    <textarea
      v-if="showDetails && botStore.activeBot.strategy"
      v-model="strategyCode"
      class="h-full w-full rounded-xl border border-default/70 bg-default p-3 font-mono text-xs"
    ></textarea>
  </div>
</template>
