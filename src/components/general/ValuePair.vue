<script setup lang="ts">
withDefaults(
  defineProps<{
    description: string;
    help?: string;
    classLabel?: string;
    classValue?: string;
  }>(),
  {
    help: '',
    classLabel: 'w-4/12 font-medium text-muted mb-0',
    classValue: 'w-8/12',
  },
);
</script>

<template>
  <div class="flex w-full text-sm">
    <div class="flex justify-between me-2 items-center gap-2" :class="classLabel">
      <label>{{ description }}</label>
      <InfoBox v-if="help" :hint="help" />
    </div>
    <div :class="classValue">
      <slot></slot>
    </div>
  </div>
</template>
