<script setup lang="ts">
import { I18nT } from 'vue-i18n';
import novaeonWordmark from '@/assets/novaeon-wordmark.svg';

definePage({
  meta: {
    allowAnonymous: true,
  },
});

const { t } = useI18n();
const botStore = useBotStore();
const loginDialog = useLoginDialog();
</script>

<template>
  <div class="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-6 text-left sm:px-6 sm:py-8">
    <header>
      <h1 class="text-2xl font-semibold text-balance text-highlighted">{{ t('bots.title') }}</h1>
      <p class="mt-1 text-sm text-pretty text-muted">
        {{ t('bots.intro') }}
      </p>
    </header>

    <BotList v-if="botStore.botCount > 0" />
    <section
      v-else
      class="nova-panel flex flex-col items-center gap-4 p-8 text-center"
      :aria-label="t('bots.emptyAria')"
    >
      <span class="flex size-12 items-center justify-center rounded-full bg-accented">
        <UIcon name="i-mdi-robot-outline" class="size-6 text-brand-400" />
      </span>
      <p class="max-w-sm text-sm text-pretty text-muted">
        {{ t('bots.empty') }}
      </p>
      <UButton
        color="primary"
        variant="solid"
        icon="i-mdi-link-variant"
        :label="t('bots.connect')"
        class="px-4 font-semibold"
        @click="loginDialog({})"
      />
    </section>

    <section
      class="nova-panel flex items-center gap-4 p-4 sm:p-6"
      :aria-label="t('bots.aboutAria')"
    >
      <AppIcon class="mx-0! h-12 w-12 shrink-0" />
      <div class="min-w-0">
        <AppText class="text-base!" />
        <p class="mt-1 text-sm text-pretty text-muted">
          {{ t('bots.about') }}
        </p>
      </div>
    </section>

    <footer
      class="flex flex-wrap items-center justify-center gap-x-1.5 gap-y-1 pt-2 text-xs text-muted"
    >
      <span>{{ t('general.madeBy') }}</span>
      <img :src="novaeonWordmark" alt="novæon" class="inline-block h-3 w-auto" />
      <span aria-hidden="true">·</span>
      <I18nT keypath="general.openSource" tag="span" scope="global">
        <template #license>
          <a
            class="rounded-sm text-default underline decoration-default underline-offset-4 hover:text-highlighted focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-400/60"
            href="https://www.gnu.org/licenses/gpl-3.0.html"
            target="_blank"
            rel="noopener noreferrer"
            >GPL-3.0</a
          >
        </template>
      </I18nT>
    </footer>
  </div>
</template>
