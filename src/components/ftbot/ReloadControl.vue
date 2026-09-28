<script setup lang="ts">
const { t } = useI18n();
const botStore = useBotStore();
const autoRefreshLoc = computed({
  get() {
    return botStore.globalAutoRefresh;
  },
  set(newValue: boolean) {
    botStore.setGlobalAutoRefresh(newValue);
  },
});
</script>

<template>
  <div class="flex items-center gap-0.5" role="group" :aria-label="t('bot.reload.group')">
    <UTooltip :text="autoRefreshLoc ? t('bot.reload.autoOn') : t('bot.reload.autoOff')">
      <UButton
        color="neutral"
        variant="ghost"
        size="sm"
        :icon="autoRefreshLoc ? 'i-mdi-sync' : 'i-mdi-sync-off'"
        :class="autoRefreshLoc ? 'text-brand-400' : 'text-muted'"
        :aria-pressed="autoRefreshLoc"
        :aria-label="t('bot.reload.auto')"
        @click="autoRefreshLoc = !autoRefreshLoc"
      />
    </UTooltip>
    <UTooltip :text="t('bot.reload.refreshNow')">
      <UButton
        color="neutral"
        variant="ghost"
        size="sm"
        icon="i-mdi-refresh"
        :aria-label="t('bot.reload.refreshNow')"
        @click="botStore.allRefreshFull"
      />
    </UTooltip>
  </div>
</template>
