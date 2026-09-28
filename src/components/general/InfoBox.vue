<script setup lang="ts">
defineProps<{ hint: string }>();
</script>

<template>
  <UTooltip :text="hint" :ui="{ content: 'h-auto max-w-xs py-1.5', text: 'whitespace-normal' }">
    <span
      tabindex="0"
      role="img"
      :aria-label="hint"
      class="inline-flex rounded-full text-muted transition-colors duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] hover:text-default focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-400/60"
    >
      <UIcon name="i-mdi-information-outline" class="size-4" />
    </span>
  </UTooltip>
</template>
