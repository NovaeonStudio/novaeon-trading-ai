<script setup lang="ts">
const locFreqaiModel = defineModel<string>();
const { t } = useI18n();
const botStore = useBotStore();

onMounted(() => {
  if (botStore.activeBot.freqaiModelList.length === 0) {
    botStore.activeBot.getFreqAIModelList();
  }
});
</script>

<template>
  <div class="flex w-full gap-2">
    <USelectMenu
      v-model="locFreqaiModel"
      :items="botStore.activeBot.freqaiModelList"
      :placeholder="t('freqai.selectModel')"
      class="w-full"
    >
    </USelectMenu>
    <UTooltip :text="t('freqai.reload')">
      <UButton
        color="neutral"
        variant="outline"
        icon="i-mdi-refresh"
        :aria-label="t('freqai.reload')"
        @click="botStore.activeBot.getFreqAIModelList()"
      />
    </UTooltip>
  </div>
</template>
