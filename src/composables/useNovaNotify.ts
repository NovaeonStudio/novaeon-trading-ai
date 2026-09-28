/**
 * Browser notifications for important bot events while the app is open (also in a background tab):
 * buys, sells, bot not responding, emergency brake. Opt-in, stored per browser.
 */
import { t as tr } from '@/i18n';

const enabled = useStorage('nova-notify', false);
let started = false;

function notify(title: string, body: string, tag: string) {
  if (
    !enabled.value ||
    typeof Notification === 'undefined' ||
    Notification.permission !== 'granted'
  )
    return;
  try {
    new Notification(title, { body, tag, icon: '/icon-192.png', badge: '/icon-192.png' });
  } catch {
    // some mobile browsers only allow notifications from a service worker
    navigator.serviceWorker?.ready.then((reg) =>
      reg.showNotification(title, { body, tag, icon: '/icon-192.png' }),
    );
  }
}

export function useNovaNotify() {
  const botStore = useBotStore();
  const { healthy } = useNovaLive();
  const { simple } = useNovaMode();

  async function toggle() {
    if (enabled.value) {
      enabled.value = false;
      return;
    }
    if (typeof Notification === 'undefined') return;
    const perm =
      Notification.permission === 'granted' ? 'granted' : await Notification.requestPermission();
    enabled.value = perm === 'granted';
    if (enabled.value) notify('NovaeonTradingAI', tr('toasts.notify.on'), 'nova-on');
  }

  if (!started) {
    started = true;
    let knownOpen: Set<number> | null = null;
    let knownClosed: Set<number> | null = null;
    watch(
      () => [botStore.activeBot?.openTrades ?? [], botStore.activeBot?.closedTrades ?? []] as const,
      ([open, closed]) => {
        const cur = botStore.activeBot?.botState?.stake_currency ?? '';
        if (knownOpen && knownClosed) {
          for (const t of open)
            if (!knownOpen.has(t.trade_id) && !knownClosed.has(t.trade_id))
              notify(
                tr('toasts.notify.bought', { coin: t.pair.split('/')[0] }),
                tr('toasts.notify.boughtBody', {
                  amount: novaMoney(t.stake_amount, cur, 0),
                  price: formatPrice(t.open_rate, 6),
                }),
                `buy-${t.trade_id}`,
              );
          for (const t of closed)
            if (!knownClosed.has(t.trade_id)) {
              const win = (t.profit_abs ?? 0) >= 0;
              const body = {
                amount: novaMoney(Math.abs(t.profit_abs ?? 0), cur, 2),
                reason: simple.value ? plainExitReason(t.exit_reason) : (t.exit_reason ?? ''),
              };
              notify(
                tr('toasts.notify.sold', {
                  coin: t.pair.split('/')[0],
                  pct: novaPct(t.profit_ratio, 2, true),
                }),
                win ? tr('toasts.notify.soldProfit', body) : tr('toasts.notify.soldLoss', body),
                `sell-${t.trade_id}`,
              );
            }
        }
        if (open.length || closed.length) {
          knownOpen = new Set(open.map((t) => t.trade_id));
          knownClosed = new Set(closed.map((t) => t.trade_id));
        }
      },
    );
    watch(healthy, (ok, was) => {
      if (was && !ok)
        notify(tr('toasts.notify.notResponding'), tr('toasts.notify.notRespondingBody'), 'health');
      if (!was && ok && was !== undefined)
        notify(tr('toasts.notify.back'), tr('toasts.notify.backBody'), 'health');
    });
    watch(
      () =>
        (botStore.activeBot?.activeLocks ?? []).some(
          (l) => (l.pair === '*' || l.pair === 'all') && l.lock_end_timestamp > Date.now(),
        ),
      (brake, was) => {
        if (brake && !was)
          notify(tr('toasts.notify.brake'), tr('toasts.notify.brakeBody'), 'brake');
      },
    );
  }

  return { notifyEnabled: enabled, toggleNotify: toggle };
}
