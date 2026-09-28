<script setup lang="ts">
definePage({
  meta: {
    allowAnonymous: true,
  },
});
const { t } = useI18n();
</script>

<template>
  <div class="flex min-h-full items-start justify-center px-4 py-10 sm:items-center sm:py-16">
    <section class="nova-panel w-full max-w-md p-6 text-left sm:p-8" aria-labelledby="login-title">
      <div class="mb-6 flex flex-col items-start gap-4">
        <AppIcon class="mx-0! h-12 w-12" />
        <div>
          <h1 id="login-title" class="text-2xl font-semibold text-balance text-highlighted">
            {{ t('login.title') }}
          </h1>
          <p class="mt-1 text-sm text-pretty text-muted">
            {{ t('login.intro') }}
          </p>
        </div>
      </div>
      <BotLogin />
    </section>
  </div>
</template>
