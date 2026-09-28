<script setup lang="ts">
const { t } = useI18n();
</script>

<template>
  <div
    class="mx-auto flex w-full max-w-[1680px] flex-col gap-6 px-4 py-6 text-left sm:px-6 sm:py-8"
  >
    <header>
      <h1 class="text-2xl font-semibold text-balance text-highlighted">
        {{ t('analysis.lookahead.title') }}
      </h1>
      <p class="mt-1 text-sm text-pretty text-muted">
        {{ t('analysis.lookahead.subtitle') }}
      </p>
    </header>
    <LookaheadAnalysis />
  </div>
</template>
