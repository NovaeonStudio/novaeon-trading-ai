<script setup lang="ts">
/** The standard card: title + optional subtitle and actions, then content. Same surface as Simple mode. */
defineProps<{ title?: string; subtitle?: string }>();
</script>

<template>
  <section class="nova-panel flex min-w-0 flex-col p-4 sm:p-6">
    <header
      v-if="title || $slots.actions"
      class="mb-4 flex flex-wrap items-start justify-between gap-3"
    >
      <div class="min-w-0">
        <h2 class="text-base font-semibold text-balance text-highlighted">{{ title }}</h2>
        <p v-if="subtitle" class="mt-1 text-sm text-pretty text-muted">{{ subtitle }}</p>
      </div>
      <slot name="actions" />
    </header>
    <div class="min-h-0 flex-1">
      <slot />
    </div>
  </section>
</template>
