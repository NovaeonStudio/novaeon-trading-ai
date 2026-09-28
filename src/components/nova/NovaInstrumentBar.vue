<script setup lang="ts">
/** Live instrument cluster for the header: heartbeat, mode, equity, today, positions, BTC regime. */
const { bot, healthy, heartbeatAgeMs, now, equity, startCapital, todayPnl, unrealized, regime } =
  useNovaLive();
const { privacy, togglePrivacy } = useNovaPrivacy();
const { togglePalette } = useNovaPalette();
const { simple } = useNovaMode();
const { notifyEnabled, toggleNotify } = useNovaNotify();

const currency = computed(() => bot.value?.botState?.stake_currency ?? '');
const openCount = computed(() => bot.value?.openTrades?.length ?? 0);
const maxTrades = computed(() => bot.value?.botState?.max_open_trades ?? 0);
const change = computed(() => (startCapital.value ? equity.value / startCapital.value - 1 : 0));
const online = computed(() => !!bot.value?.isBotOnline);
</script>

<template>
  <div class="flex items-center gap-1">
    <div
      v-if="online"
      class="nova-num hidden items-stretch divide-x divide-default/70 rounded-xl border border-default/70 bg-elevated/40 xl:flex"
    >
      <div
        class="flex items-center gap-2 px-3 py-1"
        :title="
          $t('widgets.heartbeatTitle', {
            age: novaAge(
              heartbeatAgeMs !== null ? now.getTime() - heartbeatAgeMs : null,
              now.getTime(),
            ),
          })
        "
      >
        <span class="relative flex size-2">
          <span
            v-if="healthy"
            class="absolute inline-flex size-full animate-ping rounded-full bg-emerald-400/60"
          />
          <span
            class="relative inline-flex size-2 rounded-full"
            :class="healthy ? 'bg-emerald-400' : 'bg-rose-500'"
          />
        </span>
        <span
          class="rounded-full px-2 py-0.5 text-xs font-semibold"
          :class="
            bot?.botState?.dry_run
              ? 'bg-secondary/15 text-secondary'
              : 'bg-rose-500/15 text-rose-400'
          "
          >{{
            bot?.botState?.dry_run
              ? simple
                ? $t('widgets.mode.practice')
                : $t('widgets.mode.paper')
              : simple
                ? $t('widgets.mode.realMoney')
                : $t('widgets.mode.live')
          }}</span
        >
      </div>
      <div class="px-3 py-1 leading-tight">
        <div class="text-xs text-dimmed">
          {{ simple ? $t('widgets.instrumentBar.yourMoney') : $t('widgets.metrics.equity') }}
        </div>
        <div class="text-sm font-semibold whitespace-nowrap text-highlighted">
          <span class="nova-money">{{ novaMoney(equity, '', 2) }}</span>
          <span class="ms-1 text-xs" :class="change >= 0 ? 'text-emerald-400' : 'text-rose-400'">{{
            novaPct(change, 1, true)
          }}</span>
        </div>
      </div>
      <div class="px-3 py-1 leading-tight">
        <div class="text-xs text-dimmed">{{ $t('widgets.metrics.today') }}</div>
        <div
          class="nova-money text-sm font-semibold"
          :class="todayPnl >= 0 ? 'text-emerald-400' : 'text-rose-400'"
        >
          {{ novaMoney(todayPnl, '', 2, true) }}
        </div>
      </div>
      <div class="px-3 py-1 leading-tight">
        <div class="text-xs whitespace-nowrap text-dimmed">
          {{
            simple
              ? $t('widgets.instrumentBar.coinsHeld', openCount)
              : $t('widgets.instrumentBar.openOf', { open: openCount, max: maxTrades })
          }}
        </div>
        <div
          class="nova-money text-sm font-semibold"
          :class="unrealized >= 0 ? 'text-emerald-400' : 'text-rose-400'"
        >
          {{ novaMoney(unrealized, '', 2, true) }}
        </div>
      </div>
      <div
        v-if="regime && !simple"
        class="px-3 py-1 leading-tight"
        :title="$t('widgets.instrumentBar.regimeTitle')"
      >
        <div class="text-xs text-dimmed">{{ $t('widgets.instrumentBar.btcRegime') }}</div>
        <div class="text-sm font-semibold whitespace-nowrap text-highlighted">
          {{ novaMoney(regime.btc, '', 0) }}
          <span
            class="ms-1 text-xs"
            :class="regime.strength >= 0 ? 'text-emerald-400' : 'text-rose-400'"
          >
            {{ regime.strength >= 0 ? $t('widgets.regime.on') : $t('widgets.regime.off') }}
          </span>
        </div>
      </div>
    </div>
    <span v-if="currency && online" class="sr-only">{{ currency }}</span>

    <UTooltip
      :text="
        notifyEnabled ? $t('widgets.instrumentBar.notifyOn') : $t('widgets.instrumentBar.notifyOff')
      "
    >
      <UButton
        color="neutral"
        variant="ghost"
        size="sm"
        :icon="notifyEnabled ? 'i-mdi-bell-ring-outline' : 'i-mdi-bell-off-outline'"
        :aria-label="$t('widgets.instrumentBar.toggleNotify')"
        @click="toggleNotify"
      />
    </UTooltip>
    <UTooltip
      :text="
        privacy
          ? $t('widgets.instrumentBar.showBalances')
          : $t('widgets.instrumentBar.hideBalances')
      "
    >
      <UButton
        color="neutral"
        variant="ghost"
        size="sm"
        :icon="privacy ? 'i-mdi-eye-off' : 'i-mdi-eye'"
        :aria-label="$t('widgets.instrumentBar.togglePrivacy')"
        @click="togglePrivacy"
      />
    </UTooltip>
    <UButton
      color="neutral"
      variant="outline"
      size="sm"
      class="hidden rounded-lg md:inline-flex"
      icon="i-mdi-magnify"
      :aria-label="$t('widgets.instrumentBar.openPalette')"
      @click="togglePalette"
    >
      <span class="text-xs text-muted">{{ $t('common.search') }}</span>
      <UKbd value="meta" size="sm" /><UKbd value="K" size="sm" />
    </UButton>
  </div>
</template>
