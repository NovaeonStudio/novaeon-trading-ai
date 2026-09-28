<script setup lang="ts">
const { t } = useI18n();
const botStore = useBotStore();
</script>

<template>
  <USelect
    v-if="botStore.botCount > 1"
    :model-value="botStore.selectedBot"
    label-key="botName"
    value-key="botId"
    size="sm"
    class="min-w-36"
    :aria-label="t('bots.select')"
    :items="botStore.availableBotsSorted"
    @update:model-value="botStore.selectBot($event)"
  >
    <template #item="{ item }">
      <BotEntry :bot="item" no-buttons no-refresh-switch />
    </template>
  </USelect>
</template>
