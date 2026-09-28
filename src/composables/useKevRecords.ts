/**
 * Sentinel decision records (trade custom data key "kev", the model's former name), shared by every view.
 *
 * Load-aware on purpose (a burst of parallel custom-data requests helped exhaust the engine's DB pool):
 * each trade is asked about at most once (records never change after the entry fill), requests run
 * one after another, and one poller serves all consumers. Only very fresh trades (entry order not
 * filled yet, or opened < 10 min ago) are re-checked.
 * Note: the bulk endpoint /trades/open/custom-data returns 404 even when data exists, so we query
 * per trade.
 */
import type { KevRecord } from '@/components/nova/kev';

const records = ref(new Map<number, KevRecord>());
const checked = new Set<number>();
let consumers = 0;
let timer: ReturnType<typeof setInterval> | undefined;
let running = false;
let botKey = '';

function isFresh(t: { open_timestamp: number; has_open_orders?: boolean; is_open: boolean }) {
  return t.is_open && (!!t.has_open_orders || Date.now() - t.open_timestamp < 10 * 60_000);
}

async function refresh(recentClosed = 25) {
  const botStore = useBotStore();
  const bot = botStore.activeBot;
  if (!bot?.isBotOnline || running) return;
  if (botKey !== botStore.selectedBot) {
    botKey = botStore.selectedBot;
    records.value = new Map();
    checked.clear();
  }
  running = true;
  try {
    const recent = [...bot.closedTrades]
      .sort((a, b) => b.close_timestamp - a.close_timestamp)
      .slice(0, recentClosed);
    const todo = [...bot.openTrades, ...recent].filter(
      (t) => !records.value.has(t.trade_id) && (!checked.has(t.trade_id) || isFresh(t)),
    );
    if (!todo.length) return;
    const next = new Map(records.value);
    for (const t of todo) {
      const res = await bot.getCustomDataQuiet(t.trade_id);
      const kev = res?.[0]?.custom_data.find((c) => c.key === 'kev');
      if (kev) next.set(t.trade_id, kev.value as KevRecord);
      checked.add(t.trade_id);
    }
    records.value = next;
  } finally {
    running = false;
  }
}

export function useKevRecords() {
  const botStore = useBotStore();
  onMounted(() => {
    consumers += 1;
    if (consumers === 1) timer = setInterval(() => refresh(), 60_000);
    refresh();
  });
  onUnmounted(() => {
    consumers -= 1;
    if (consumers === 0 && timer) {
      clearInterval(timer);
      timer = undefined;
    }
  });
  // New trades appear after load / entry fill: only unseen ids trigger requests.
  watch(
    () =>
      [...(botStore.activeBot?.openTrades ?? []), ...(botStore.activeBot?.closedTrades ?? [])]
        .map((t) => t.trade_id)
        .join(','),
    () => refresh(),
  );
  return { kevRecords: records, refreshKev: () => refresh() };
}
