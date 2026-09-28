/**
 * Shared live data for the NovaeonTradingAI header, Command Center and Cockpit.
 * One poller for all consumers (ref-counted), so opening several views never multiplies API calls.
 */
import { TimeSummaryOptions } from '@/types';

interface NovaRegime {
  /** BTC daily close vs its 50-day EMA, as ratio (0.1 = 10 % above). */
  strength: number;
  /** Latest BTC daily close as seen by the strategy. */
  btc: number;
}

const regime = ref<NovaRegime | null>(null);
const lastRefresh = ref(0);
let consumers = 0;
let timer: ReturnType<typeof setInterval> | undefined;

async function refreshRegime() {
  const bot = useBotStore().activeBot;
  const stake = bot?.botState?.stake_currency;
  const tf = bot?.botState?.timeframe;
  if (!stake || !tf) return;
  const pair = bot.botState?.trading_mode === 'futures' ? `BTC/${stake}:${stake}` : `BTC/${stake}`;
  const cols = await bot.getLatestColumns(pair, tf, ['btc_close_1d', 'btc_ema50_1d']);
  regime.value = cols
    ? {
        strength: (cols.btc_close_1d as number) / (cols.btc_ema50_1d as number) - 1,
        btc: cols.btc_close_1d as number,
      }
    : null;
}

async function refresh() {
  const bot = useBotStore().activeBot;
  if (!bot?.isBotOnline) return;
  await Promise.allSettled([
    bot.getHealth(),
    refreshRegime(),
    bot.getTimeSummary(TimeSummaryOptions.daily, { timescale: 84 }),
  ]);
  lastRefresh.value = Date.now();
}

export function useNovaLive() {
  const botStore = useBotStore();

  onMounted(() => {
    consumers += 1;
    if (consumers === 1) {
      refresh();
      timer = setInterval(refresh, 20_000);
    }
  });
  onUnmounted(() => {
    consumers -= 1;
    if (consumers === 0 && timer) {
      clearInterval(timer);
      timer = undefined;
    }
  });
  // botState arrives asynchronously after login/refresh; bot switch resets everything
  watch(
    () => [botStore.activeBot?.botState?.stake_currency, botStore.activeBot?.botState?.timeframe],
    () => refreshRegime(),
  );
  watch(
    () => botStore.activeBot?.isBotOnline,
    (online) => online && refresh(),
  );
  watch(
    () => botStore.selectedBot,
    () => {
      regime.value = null;
      refresh();
    },
  );

  const bot = computed(() => botStore.activeBot);
  const now = useNow({ interval: 1000 });
  const heartbeatAgeMs = computed(() => {
    const ts = bot.value?.health?.last_process_ts;
    return ts ? now.value.getTime() - ts * 1000 : null;
  });
  const healthy = computed(
    () => heartbeatAgeMs.value !== null && heartbeatAgeMs.value < 5 * 60_000,
  );
  const equity = computed(() => bot.value?.balance?.total ?? 0);
  const startCapital = computed(() => bot.value?.balance?.starting_capital || equity.value);
  const todayPnl = computed(() => bot.value?.dailyStats?.data?.[0]?.abs_profit ?? 0);
  const unrealized = computed(() =>
    (bot.value?.openTrades ?? []).reduce((s, t) => s + (t.profit_abs ?? 0), 0),
  );

  return {
    bot,
    now,
    regime,
    lastRefresh,
    refresh,
    heartbeatAgeMs,
    healthy,
    equity,
    startCapital,
    todayPnl,
    unrealized,
  };
}
