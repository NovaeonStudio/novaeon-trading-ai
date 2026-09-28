<script setup lang="ts">
import Favico from 'favico.js';

import type { AuthStorageWithBotId } from '@/types';
import type { DropdownMenuItem } from '@nuxt/ui';
import { breakpointsTailwind } from '@vueuse/core';
import { useRoute } from 'vue-router';

const { t } = useI18n();
const botStore = useBotStore();

const settingsStore = useSettingsStore();
const route = useRoute();
const router = useRouter();
const favicon = ref<Favico | undefined>(undefined);
const pingInterval = ref<number>();
const loginDialog = useLoginDialog();
const { sections: novaSections } = useNovaNav();
const { simple: novaSimple, mode: novaMode } = useNovaMode();
const { tabs: novaTabs } = useNovaNav();
/** Simple mode on phones: the main items live in the bottom tab bar, the menu only holds "More". */
const mobileSections = computed(() =>
  novaTabs.value.length ? novaSections.value.filter((s) => s.secondary) : novaSections.value,
);

const breakpoints = useBreakpoints(breakpointsTailwind);

const isMobile = breakpoints.smallerOrEqual('md');

async function clickLogout() {
  botStore.removeBot(botStore.selectedBot);
  // TODO: This should be per bot
  await router.push('/');
}

const setOpenTradesAsPill = (tradeCount: number) => {
  if (!favicon.value) {
    favicon.value = new Favico({
      animation: 'none',
      // position: 'up',
      // fontStyle: 'normal',
      // bgColor: '#',
      // textColor: '#FFFFFF',
    });
  }
  if (tradeCount !== 0 && settingsStore.openTradesInTitle === 'showPill') {
    favicon.value.badge(tradeCount);
  } else {
    favicon.value.reset();
    console.log('reset');
  }
};
const setTitle = () => {
  let title = 'NovaeonTradingAI';
  if (settingsStore.openTradesInTitle === OpenTradeVizOptions.asTitle) {
    title = `(${botStore.activeBot?.openTradeCount}) ${title}`;
  }
  if (botStore.activeBot?.botName) {
    title = `${title} - ${botStore.activeBot?.botName}`;
  }
  document.title = title;
};

onBeforeUnmount(() => {
  if (pingInterval.value) {
    clearInterval(pingInterval.value);
  }
});

onMounted(async () => {
  await settingsStore.loadUIVersion();
  pingInterval.value = window.setInterval(botStore.pingAll, 60000);
});

settingsStore.$subscribe((_, state) => {
  const needsUpdate = settingsStore.openTradesInTitle !== state.openTradesInTitle;
  if (needsUpdate) {
    setTitle();
    setOpenTradesAsPill(botStore.activeBot?.openTradeCount || 0);
  }
});

watch(
  () => botStore.activeBot?.botName,
  () => setTitle(),
);
watch(
  () => botStore.activeBot?.openTradeCount,
  () => {
    if (settingsStore.openTradesInTitle === OpenTradeVizOptions.showPill) {
      setOpenTradesAsPill(botStore.activeBot?.openTradeCount ?? 0);
    } else if (settingsStore.openTradesInTitle === OpenTradeVizOptions.asTitle) {
      setTitle();
    }
  },
);

const menuItems = computed<DropdownMenuItem[][]>(() => [
  [
    {
      label: t('common.version', { version: uiVersionShort.value }),
      disabled: true,
    },
  ],
  [
    {
      label: t('nav.item.settings'),
      icon: 'i-mdi-cog',
      onSelect: () => router.push('/settings'),
    },
  ],
  ...(botStore.hasBots && botStore.botCount === 1
    ? [
        [
          {
            label: t('menu.logout'),
            icon: 'i-mdi-logout',
            onSelect: clickLogout,
          },
        ],
      ]
    : []),
]);

/** Version without the dev build prefix, for quiet display. */
const uiVersionShort = computed(() => settingsStore.uiVersion.replace(/^not_installed-/, ''));

/** Active bot's own auto refresh (the switch on the Bots page), shown as a toggle in the Pro header. */
const activeBotAutoRefresh = computed({
  get: () => botStore.activeBot?.autoRefresh ?? false,
  set: (value: boolean) => botStore.activeBot?.setAutoRefresh(value),
});
const activeBotLabel = computed(
  () =>
    botStore.activeBot?.botName || botStore.selectedBotObj?.botName || t('header.noBotSelected'),
);

function editBotLogin(botId: string) {
  const bot = botStore.botStores[botId];
  if (!bot) {
    showAlert(t('header.botNotFound'), 'warning');
    return;
  }
  const loginInfo: AuthStorageWithBotId = {
    ...bot.getLoginInfo(),
    botId,
  };

  loginDialog({ loginInfo: loginInfo });
}
</script>

<template>
  <header class="relative z-40">
    <NovaCommandPalette />
    <div class="nova-header flex h-14 items-center gap-2 px-3">
      <RouterLink
        class="flex shrink-0 items-center gap-2 rounded-lg pe-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-400/60"
        exact
        to="/"
        :aria-label="t('header.homeLink')"
      >
        <AppIcon class="h-8 w-8" />
        <AppText class="hidden lg:inline" />
      </RouterLink>
      <div class="flex min-w-0 flex-1 items-center justify-end gap-2">
        <!-- Right aligned nav items -->
        <template v-if="!isMobile">
          <NovaInstrumentBar />
          <UTooltip v-if="!settingsStore.confirmDialog" :text="t('header.noConfirmTooltip')">
            <RouterLink
              to="/settings"
              class="flex h-8 items-center gap-1.5 rounded-full bg-amber-500/15 px-3 text-xs font-medium text-amber-400 transition duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] hover:bg-amber-500/25 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-400/60"
              :aria-label="t('header.noConfirmAria')"
            >
              <UIcon name="i-mdi-alert-outline" class="size-4" />
              <span class="hidden xl:inline">{{ t('header.noConfirm') }}</span>
            </RouterLink>
          </UTooltip>
          <!-- Pro: bot status and refresh controls, grouped like the instrument bar -->
          <div
            v-if="!novaSimple && botStore.hasBots"
            class="flex h-10 items-center gap-0.5 rounded-xl border border-default/70 bg-elevated/40 ps-3 pe-1"
            role="group"
            :aria-label="t('header.botConnection')"
          >
            <UTooltip
              :text="
                !botStore.activeBot?.isBotLoggedIn
                  ? t('header.loginExpired')
                  : botStore.activeBot?.isBotOnline
                    ? t('header.botOnline')
                    : t('header.botOffline')
              "
            >
              <span class="flex items-center gap-2 pe-1">
                <span
                  class="inline-flex size-2 rounded-full"
                  :class="
                    botStore.activeBot?.isBotLoggedIn && botStore.activeBot?.isBotOnline
                      ? 'bg-emerald-400'
                      : 'bg-rose-500'
                  "
                />
                <span
                  v-if="botStore.botCount <= 1"
                  class="hidden max-w-32 truncate text-sm font-medium text-default 2xl:inline"
                  >{{ activeBotLabel }}</span
                >
                <span class="sr-only">{{
                  botStore.activeBot?.isBotOnline ? t('common.online') : t('common.offline')
                }}</span>
              </span>
            </UTooltip>
            <BotSelect />
            <UTooltip v-if="!botStore.activeBot?.isBotLoggedIn" :text="t('bots.logInAgain')">
              <UButton
                color="neutral"
                variant="ghost"
                size="sm"
                icon="i-mdi-login"
                :aria-label="t('bots.logInAgain')"
                @click="editBotLogin(botStore.selectedBot)"
              />
            </UTooltip>
            <!-- Per bot switch: shown with several bots, or when it is off (it then blocks refreshing). -->
            <UTooltip
              v-if="botStore.botCount > 1 || !activeBotAutoRefresh"
              :text="
                activeBotAutoRefresh
                  ? t('header.autoRefreshOn', { bot: activeBotLabel })
                  : t('header.autoRefreshOff', { bot: activeBotLabel })
              "
            >
              <UButton
                color="neutral"
                variant="ghost"
                size="sm"
                :icon="activeBotAutoRefresh ? 'i-mdi-autorenew' : 'i-mdi-autorenew-off'"
                :class="activeBotAutoRefresh ? 'text-brand-400' : 'text-muted'"
                :aria-pressed="activeBotAutoRefresh"
                :aria-label="t('bots.autoRefreshFor', { name: activeBotLabel })"
                @click="activeBotAutoRefresh = !activeBotAutoRefresh"
              />
            </UTooltip>
            <ReloadControl />
          </div>
          <UDropdownMenu v-if="botStore.hasBots" :items="menuItems" size="lg">
            <UButton
              color="neutral"
              variant="ghost"
              size="sm"
              trailing-icon="i-mdi-chevron-down"
              :aria-label="t('header.appMenu')"
              class="focus-visible:ring-2 focus-visible:ring-brand-400/60"
            >
              <AppIcon class="h-5 w-5" />
            </UButton>
          </UDropdownMenu>
          <UButton
            v-else-if="route?.path !== '/login'"
            color="primary"
            variant="soft"
            size="sm"
            icon="i-mdi-login"
            :label="t('header.connectBot')"
            @click="loginDialog({})"
          />
        </template>

        <!-- Mobile menu -->
        <USlideover
          v-if="isMobile"
          direction="right"
          :close="{
            color: 'neutral',
            variant: 'ghost',
            class: 'rounded-full',
          }"
        >
          <UButton
            color="neutral"
            variant="ghost"
            size="lg"
            icon="i-mdi-menu"
            :aria-label="t('menu.open')"
            class="size-10 justify-center"
          />
          <template #title>
            <div class="flex flex-row items-center gap-2">
              <AppIcon class="h-8 w-8" />
              <AppText />
            </div>
          </template>
          <template #body="{ close }">
            <div class="flex h-full flex-col gap-6 text-start">
              <nav class="flex w-full flex-col gap-4" :aria-label="t('nav.main')">
                <div v-for="section in mobileSections" :key="section.id">
                  <div class="nova-label mb-1 px-3">
                    {{ section.label }}
                  </div>
                  <RouterLink
                    v-for="item in section.items"
                    :key="item.to"
                    :to="item.to"
                    class="flex min-h-10 items-center gap-3 rounded-xl px-3 py-2 text-sm text-default transition duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] hover:bg-accented/60 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-400/60 active:scale-[0.98]"
                    active-class="bg-brand-400/10 text-highlighted"
                    @click="close"
                  >
                    <UIcon :name="item.icon" class="size-5 text-brand-400" />{{ item.label }}
                  </RouterLink>
                </div>
              </nav>
              <div class="flex flex-col gap-2">
                <div class="nova-label px-3">{{ t('menu.view') }}</div>
                <div class="nova-seg grid! w-full grid-cols-2 text-sm">
                  <button
                    v-for="m in ['simple', 'pro'] as const"
                    :key="m"
                    type="button"
                    class="min-h-10 font-medium"
                    :aria-pressed="novaMode === m"
                    @click="novaMode = m"
                  >
                    {{ m === 'simple' ? t('common.simple') : t('common.pro') }}
                  </button>
                </div>
              </div>
              <div class="flex flex-col gap-2">
                <div class="nova-label px-3">{{ $t('common.language') }}</div>
                <LanguageSelect />
              </div>
              <div v-if="botStore.hasBots" class="flex flex-col gap-2">
                <div class="nova-label px-3">{{ t('menu.bot') }}</div>
                <div class="nova-tile flex flex-col gap-3 p-3">
                  <div class="flex items-center gap-2 text-sm">
                    <span
                      class="inline-flex size-2 shrink-0 rounded-full"
                      :class="
                        botStore.activeBot?.isBotLoggedIn && botStore.activeBot?.isBotOnline
                          ? 'bg-emerald-400'
                          : 'bg-rose-500'
                      "
                    />
                    <span class="min-w-0 flex-1 truncate font-medium text-highlighted">{{
                      activeBotLabel
                    }}</span>
                    <span class="text-xs text-muted">{{
                      botStore.activeBot?.isBotOnline ? t('common.online') : t('common.offline')
                    }}</span>
                  </div>
                  <BotSelect class="w-full" />
                  <UButton
                    v-if="!botStore.activeBot?.isBotLoggedIn"
                    color="primary"
                    variant="soft"
                    icon="i-mdi-login"
                    :label="t('bots.logInAgain')"
                    block
                    @click="
                      close();
                      editBotLogin(botStore.selectedBot);
                    "
                  />
                  <div class="flex items-center justify-between gap-2">
                    <span class="text-sm text-muted">{{ t('menu.autoRefresh') }}</span>
                    <USwitch
                      v-model="activeBotAutoRefresh"
                      :aria-label="t('bots.autoRefreshFor', { name: activeBotLabel })"
                    />
                  </div>
                  <div class="flex items-center justify-between gap-2">
                    <span class="text-sm text-muted">{{ t('menu.allBots') }}</span>
                    <ReloadControl />
                  </div>
                </div>
              </div>
              <div
                class="mt-auto flex items-center justify-between gap-2 border-t border-default/70 pt-3"
              >
                <ThemeSelect show-text />
                <span class="text-xs text-dimmed">{{
                  t('common.version', { version: uiVersionShort })
                }}</span>
              </div>
            </div>
          </template>
        </USlideover>
      </div>
    </div>
  </header>
</template>
