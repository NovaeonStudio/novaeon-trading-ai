<script setup lang="ts">
const { t } = useI18n();
</script>

<template>
  <div class="flex min-h-full items-center justify-center px-4 py-16">
    <section class="nova-panel flex w-full max-w-md flex-col items-center gap-4 p-8 text-center">
      <span class="flex size-14 items-center justify-center rounded-full bg-accented">
        <UIcon name="i-mdi-compass-off-outline" class="size-7 text-brand-400" />
      </span>
      <div>
        <p class="nova-label">{{ t('notFound.label') }}</p>
        <h1 class="mt-1 text-2xl font-semibold text-balance text-highlighted">
          {{ t('notFound.title') }}
        </h1>
        <p class="mt-2 text-sm text-pretty text-muted">
          {{ t('notFound.text') }}
        </p>
      </div>
      <UButton
        to="/"
        color="primary"
        variant="solid"
        icon="i-mdi-arrow-left"
        :label="t('notFound.back')"
        class="px-4 font-semibold"
      />
    </section>
  </div>
</template>
