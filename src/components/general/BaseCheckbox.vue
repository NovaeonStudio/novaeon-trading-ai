<script setup lang="ts">
// TODO: This component is currently just a wrapper around UCheckbox and could be removed.
withDefaults(defineProps<{ disabled?: boolean }>(), {
  disabled: false,
});
const value = defineModel<boolean>();
</script>

<template>
  <div class="flex items-center text-start">
    <UCheckbox
      v-model="value"
      :disabled="disabled"
      :ui="{ label: 'text-sm font-medium text-highlighted', description: 'text-sm text-muted' }"
    >
      <template #label><slot /></template>
      <template #description>
        <slot name="hint"></slot>
      </template>
    </UCheckbox>
  </div>
</template>
