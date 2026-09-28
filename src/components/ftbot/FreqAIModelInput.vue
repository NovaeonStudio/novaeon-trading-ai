<script setup lang="ts">
import type { BacktestFreqAIInput } from '@/types';

const { t } = useI18n();
const freqAI = defineModel<BacktestFreqAIInput>({ required: true });
</script>

<template>
  <div class="flex flex-col gap-4">
    <div class="nova-tile p-4">
      <BaseCheckbox id="enable-freqai" v-model="freqAI.enabled">
        {{ t('freqai.enable') }}
        <template #hint>
          {{ t('freqai.enableHint') }}
        </template>
      </BaseCheckbox>
    </div>

    <div v-if="freqAI.enabled" class="grid grid-cols-1 gap-4 sm:grid-cols-2">
      <UFormField :label="t('freqai.identifier')">
        <UInput
          id="freqai-identifier"
          v-model="freqAI.identifier"
          :placeholder="t('freqai.useConfigDefault')"
          class="w-full"
        ></UInput>
      </UFormField>
      <UFormField :label="t('freqai.model')">
        <FreqaiModelSelect id="freqai-model" v-model="freqAI.model"></FreqaiModelSelect>
      </UFormField>
    </div>
  </div>
</template>
