/**
 * Wallet connection (MetaMask -> Hyperliquid API wallet) and the practice/real-money switch.
 * Talks to the control service (bot/bin/control.py) under `/control` on the same host as the engine API,
 * authenticated with the engine login token. MetaMask is used through the plain EIP-1193 provider.
 */
import axios from 'axios';
import { t } from '@/i18n';

export interface NovaBalance {
  perp: number;
  spot_usdc: number;
  total: number;
  error: string | null;
}

export interface NovaControlStatus {
  mode: 'paper' | 'live';
  since: number | null;
  capital: number | null;
  wallet: {
    address: string | null;
    agentAddress: string | null;
    approved: boolean;
    approvedAt: number | null;
    balance: NovaBalance | null;
  };
  engine: {
    online: boolean;
    dry_run: boolean | null;
    state: string | null;
    open_trades: number | null;
  };
  confirmPhrase: string;
  minCapital: number;
}

/** Practice-money ledger (paper trading). `dry_run_wallet` = start amount + every top-up. */
export interface NovaPractice {
  dry_run_wallet: number;
  started_with: number;
  /** Unix seconds, null when practice was never started over from the UI. */
  started_at: number | null;
  added: { ts: number; amount: number }[];
  db: string;
  total_added: number;
  max: number;
}

/** Result of a practice change: the new amount and whether the engine came back in time. */
export interface NovaPracticeChange {
  dry_run_wallet: number;
  engineBack: boolean;
}

/** A stop the user set by hand for one open trade (control service, GET /stops). */
export interface NovaManualStop {
  price: number;
  /** Unix seconds. */
  set_at: number;
  pair?: string;
  open_timestamp?: number;
  stop_loss_abs?: number | null;
  /** False once the trade is closed or the override no longer applies. */
  active?: boolean;
}

/** Answer of POST /control/trades/{id}/stop (set, or remove with price null). */
export interface NovaStopResult {
  ok: boolean;
  manual_stop: number | null;
  manual_stop_set_at?: number | null;
  /** The engine took the new stop. */
  applied?: boolean;
  /** The price was already below the new stop, so the position was sold right away. */
  closed?: boolean;
  /** Only when removing the override. */
  removed?: boolean;
  stop_loss_abs_before?: number | null;
  stop_loss_abs: number | null;
  distance_pct?: number | null;
  /** Plain explanation from the service (e.g. that a raised stop stays raised). */
  note?: string | null;
}

/** Engine-side levels of one open trade (GET /control/levels, /control/trades/{id}/levels). */
export interface NovaTradeLevels {
  trade_id: number;
  pair: string;
  leverage: number;
  open_rate: number;
  current_rate: number | null;
  price_tick: number | null;
  /** Entry + exit fees + funding so far. */
  break_even: number | null;
  break_even_fees_only?: number | null;
  liquidation: number | null;
  stop_loss_abs: number | null;
  initial_stop_loss_abs?: number | null;
  stop_raised?: boolean;
  manual_stop: number | null;
  manual_stop_set_at?: number | null;
  manual_stop_active?: boolean;
  entries?: number;
  enter_tag?: string | null;
  /** Per-trade endpoint only: a candle close (15m) below this = the bot sells (lowest low of the last 10 hours). */
  exit_level?: number | null;
  /** Per-trade endpoint only: the 20-candle high. */
  entry_level?: number | null;
  candle?: { timeframe: string; last_closed: number; lo10: number | null; hi20: number | null };
  btc_regime_ok?: boolean;
}

/** POST /control/buy: a new coin (Sentinel news check; Sentinel picks leverage when omitted and AI leverage is on,
 * otherwise 1×) or more of an open one. */
export interface NovaBuyRequest {
  pair: string;
  stake_amount?: number;
  /** 1–3, new coins only; omit to let Sentinel decide (1× while AI leverage is off). */
  leverage?: number;
  ordertype?: 'market' | 'limit';
}
export interface NovaBuyResult {
  ok: boolean;
  trade_id: number;
  pair: string;
  added_to_existing: boolean;
  news_checked: boolean;
  leverage: number;
  stake_amount: number;
  /** The order is still waiting for a fill. */
  order_open: boolean;
  /** Number of buys in this position after this one (max 4). */
  entries: number;
  enter_tag: string | null;
}

/**
 * Bot-wide settings (GET /control/settings). `ai_leverage`: Sentinel may pick 1–3× leverage for new trades
 * (effective value: false while locked). `ai_leverage_allowed` is false on Macs that run the smaller Sentinel build
 * (8 GB); `locked_reason` then says why in plain words.
 */
export interface NovaSettings {
  ai_leverage: boolean;
  ai_leverage_allowed: boolean;
  locked_reason: string | null;
  ram_gb: number | null;
  sentinel_build: string | null;
  max_ai_leverage: number;
  mode: 'paper' | 'live';
}

/** Answer of POST /control/settings (the engine restarts unless nothing changed). */
export interface NovaSettingsChange extends NovaSettings {
  ok: boolean;
  unchanged: boolean;
  restarting: boolean;
  open_trades?: number | null;
  note?: string;
  /** Set by the composable: the engine came back after the restart (true when there was no restart). */
  engineBack: boolean;
}

/** Most buys the control service allows per position. */
export const NOVA_MAX_BUYS = 4;

interface Eip1193 {
  request(args: { method: string; params?: unknown[] }): Promise<unknown>;
  on?(event: string, cb: (...a: unknown[]) => void): void;
  isMetaMask?: boolean;
}

const status = ref<NovaControlStatus | null>(null);
const loading = ref(false);
const error = ref<string | null>(null);
const account = ref<string | null>(null);
/** Balance of the MetaMask account while it is not yet the bot's wallet (deposit step). */
const accountBalance = ref<NovaBalance | null>(null);
const practiceInfo = ref<NovaPractice | null>(null);
/** True while the engine restarts after a practice-money change. */
const restarting = ref(false);
/** Manual stops by trade id (as string, like the control service returns them). */
const manualStops = ref<Record<string, NovaManualStop>>({});
/** Bot-wide settings (AI leverage), null until loaded. */
const botSettings = ref<NovaSettings | null>(null);
let listening = false;

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Find MetaMask itself. With several wallet extensions installed, `window.ethereum` often belongs to another
 * wallet (or a wallet-picker that intercepts requests), so prefer EIP-6963 discovery by MetaMask's rdns,
 * then the legacy `ethereum.providers` list, and only then `window.ethereum`.
 */
const announced = shallowRef<{ rdns: string; provider: Eip1193 }[]>([]);
if (typeof window !== 'undefined') {
  window.addEventListener('eip6963:announceProvider', (ev) => {
    const d = (ev as CustomEvent<{ info: { rdns: string }; provider: Eip1193 }>).detail;
    if (d?.info?.rdns && !announced.value.some((a) => a.rdns === d.info.rdns))
      announced.value = [...announced.value, { rdns: d.info.rdns, provider: d.provider }];
  });
  window.dispatchEvent(new Event('eip6963:requestProvider'));
}

function provider(): Eip1193 | undefined {
  const mm = announced.value.find(
    (a) => a.rdns === 'io.metamask' || a.rdns.startsWith('io.metamask.'),
  );
  if (mm) return mm.provider;
  const eth = (window as unknown as { ethereum?: Eip1193 & { providers?: Eip1193[] } }).ethereum;
  return eth?.providers?.find((p) => p.isMetaMask) ?? eth;
}

/** Human-readable message from an axios / MetaMask error. */
export function controlErrorText(e: unknown): string {
  const ax = e as { response?: { data?: { detail?: string } }; message?: string; code?: number };
  if (ax?.code === 4001) return t('control.cancelled');
  if (ax?.code === -32002) return t('control.pending');
  if (!ax?.response && /unexpected error/i.test(ax?.message ?? '')) return t('control.otherWallet');
  const detail = ax?.response?.data?.detail;
  if (detail) {
    if (detail.includes('Must deposit before performing actions')) return t('control.depositFirst');
    return detail;
  }
  return ax?.message ?? String(e);
}

export function useNovaControl() {
  const botStore = useBotStore();

  function client() {
    const botId = botStore.selectedBot;
    const login = useLoginInfo(botId);
    // Behind a reverse proxy the control service shares the engine's origin under /control. A local install has no
    // proxy: there it listens on the engine's port + 1 (8081 -> 8082) on the same machine; the installer keeps it so.
    const engine = new URL(login.baseUrl.value, window.location.href);
    const local = ['127.0.0.1', 'localhost'].includes(engine.hostname);
    const enginePort = Number(engine.port || (engine.protocol === 'https:' ? 443 : 80));
    const origin = local
      ? `${engine.protocol}//${engine.hostname}:${enginePort + 1}`
      : engine.origin;
    const api = axios.create({ baseURL: `${origin}/control`, timeout: 30000 });
    api.interceptors.request.use((req) => {
      req.headers.set('Authorization', `Bearer ${login.accessToken.value}`);
      return req;
    });
    api.interceptors.response.use(undefined, async (err) => {
      if (err.response?.status === 401 && !err.config._retried) {
        const token = await login.refreshToken();
        err.config._retried = true;
        err.config.headers.Authorization = `Bearer ${token}`;
        return api.request(err.config);
      }
      throw err;
    });
    return api;
  }

  async function refresh() {
    loading.value = true;
    try {
      const api = client();
      status.value = (await api.get<NovaControlStatus>('/status')).data;
      const stored = status.value.wallet.address;
      accountBalance.value =
        account.value && account.value.toLowerCase() !== stored?.toLowerCase()
          ? (await api.get<NovaBalance>(`/balance/${account.value}`)).data
          : null;
      error.value = null;
    } catch (e) {
      error.value = controlErrorText(e);
    } finally {
      loading.value = false;
    }
  }

  const hasMetaMask = computed(() => !!provider());

  async function connect(): Promise<string> {
    const p = provider();
    if (!p) throw new Error(t('control.notFound'));
    const accounts = (await p.request({ method: 'eth_requestAccounts' })) as string[];
    account.value = accounts[0] ?? null;
    if (!account.value) throw new Error(t('control.noAccount'));
    if (!listening) {
      listening = true;
      p.on?.('accountsChanged', (a) => {
        account.value = (a as string[])[0] ?? null;
        refresh();
      });
    }
    await refresh();
    return account.value;
  }

  /**
   * Let the bot trade for this wallet: the service creates a bot key, MetaMask signs Hyperliquid's ApproveAgent
   * message (EIP-712), the service submits it and stores the bot key in the Keychain.
   */
  async function approveBot() {
    const p = provider();
    if (!p) throw new Error(t('control.notFound'));
    const wallet = account.value ?? (await connect());
    const api = client();
    const { action } = (
      await api.post<{ action: Record<string, string | number> }>('/agent/start', {
        walletAddress: wallet,
      })
    ).data;
    // MetaMask requires the domain chainId to match the active network; Hyperliquid accepts any signing chain.
    const chainHex = (await p.request({ method: 'eth_chainId' })) as string;
    const typed = {
      domain: {
        name: 'HyperliquidSignTransaction',
        version: '1',
        chainId: parseInt(chainHex, 16),
        verifyingContract: '0x0000000000000000000000000000000000000000',
      },
      types: {
        EIP712Domain: [
          { name: 'name', type: 'string' },
          { name: 'version', type: 'string' },
          { name: 'chainId', type: 'uint256' },
          { name: 'verifyingContract', type: 'address' },
        ],
        'HyperliquidTransaction:ApproveAgent': [
          { name: 'hyperliquidChain', type: 'string' },
          { name: 'agentAddress', type: 'address' },
          { name: 'agentName', type: 'string' },
          { name: 'nonce', type: 'uint64' },
        ],
      },
      primaryType: 'HyperliquidTransaction:ApproveAgent',
      message: {
        hyperliquidChain: action.hyperliquidChain,
        agentAddress: action.agentAddress,
        agentName: action.agentName,
        nonce: action.nonce,
      },
    };
    const sig = (await p.request({
      method: 'eth_signTypedData_v4',
      params: [wallet, JSON.stringify(typed)],
    })) as string;
    const raw = sig.slice(2);
    let v = parseInt(raw.slice(128, 130), 16);
    if (v < 27) v += 27;
    const signature = { r: `0x${raw.slice(0, 64)}`, s: `0x${raw.slice(64, 128)}`, v };
    await api.post('/agent/confirm', {
      walletAddress: wallet,
      action: { ...action, signatureChainId: chainHex },
      signature,
    });
    await refresh();
  }

  async function forgetWallet() {
    await client().post('/wallet/forget');
    account.value = null;
    await refresh();
  }

  async function setMode(mode: 'paper' | 'live', capital?: number, confirm?: string) {
    await client().post('/mode', { mode, capital, confirm });
    await refresh();
  }

  /** Practice-money ledger (start amount, top-ups, cap). */
  async function practice(): Promise<NovaPractice> {
    practiceInfo.value = (await client().get<NovaPractice>('/practice')).data;
    return practiceInfo.value;
  }

  /**
   * After a practice change the control service restarts the engine. Poll the status until the engine is back
   * (it first has to go down, so an "online" right after the request does not count), then reload the bot data.
   */
  async function waitForEngine(timeoutMs = 120_000): Promise<boolean> {
    restarting.value = true;
    const started = Date.now();
    let sawOffline = false;
    try {
      await sleep(3000);
      while (Date.now() - started < timeoutMs) {
        await refresh();
        const online = !error.value && !!status.value?.engine.online;
        if (!online) sawOffline = true;
        else if (sawOffline || Date.now() - started > 20_000) {
          await botStore.allRefreshFull().catch(() => undefined);
          return true;
        }
        await sleep(3000);
      }
      return false;
    } finally {
      restarting.value = false;
    }
  }

  async function addPractice(amount: number): Promise<NovaPracticeChange> {
    const res = await client().post<{ ok: boolean; dry_run_wallet: number }>('/practice/add', {
      amount,
    });
    await practice().catch(() => undefined);
    const engineBack = await waitForEngine();
    return { dry_run_wallet: res.data.dry_run_wallet, engineBack };
  }

  async function resetPractice(amount: number): Promise<NovaPracticeChange> {
    const res = await client().post<{ ok: boolean; dry_run_wallet: number }>('/practice/reset', {
      amount,
      confirm: true,
    });
    await practice().catch(() => undefined);
    const engineBack = await waitForEngine();
    return { dry_run_wallet: res.data.dry_run_wallet, engineBack };
  }

  /** Manual stop overrides for open trades. */
  async function loadStops(): Promise<Record<string, NovaManualStop>> {
    manualStops.value = (await client().get<Record<string, NovaManualStop>>('/stops')).data ?? {};
    return manualStops.value;
  }

  /**
   * Move the stop of one open trade (price), or remove the manual override (null). The service rounds the price
   * to the market tick and waits (up to ~20 s) until the engine applied it. The engine only lets a stop move up;
   * errors come back as `{detail}` (read them with controlErrorText).
   */
  async function setStop(tradeId: number, price: number | null): Promise<NovaStopResult> {
    const res = (
      await client().post<NovaStopResult>(`/trades/${tradeId}/stop`, { price }, { timeout: 45000 })
    ).data;
    const next = { ...manualStops.value };
    if (res.manual_stop === null || res.manual_stop === undefined || res.closed)
      delete next[String(tradeId)];
    else
      next[String(tradeId)] = {
        price: res.manual_stop,
        set_at: res.manual_stop_set_at ?? Math.floor(Date.now() / 1000),
        stop_loss_abs: res.stop_loss_abs,
        active: true,
      };
    manualStops.value = next;
    await botStore.activeBot.getOpenTrades().catch(() => undefined);
    return res;
  }

  /** Engine-side levels (break-even incl. funding, liquidation, exit / entry level, tick) of one open trade. */
  async function tradeLevels(tradeId: number): Promise<NovaTradeLevels> {
    return (await client().get<NovaTradeLevels>(`/trades/${tradeId}/levels`)).data;
  }

  /** Buy through the control service (news check and buy limit included). */
  async function buy(req: NovaBuyRequest): Promise<NovaBuyResult> {
    const res = (await client().post<NovaBuyResult>('/buy', req, { timeout: 45000 })).data;
    await botStore.activeBot.getOpenTrades().catch(() => undefined);
    return res;
  }

  /** Bot-wide settings: AI leverage on/off/locked, memory, Sentinel build. */
  async function loadSettings(): Promise<NovaSettings> {
    botSettings.value = (await client().get<NovaSettings>('/settings')).data;
    return botSettings.value;
  }

  /**
   * Let Sentinel pick leverage (up to 3×) for new trades, or go back to 1×. Positions the bot already holds keep
   * their leverage. The engine restarts (about a minute) unless nothing changed.
   */
  async function setAiLeverage(on: boolean): Promise<NovaSettingsChange> {
    const res = (
      await client().post<Omit<NovaSettingsChange, 'engineBack'>>('/settings', { ai_leverage: on })
    ).data;
    botSettings.value = { ...res };
    const engineBack = res.restarting ? await waitForEngine() : true;
    return { ...res, engineBack };
  }

  return {
    status,
    loading,
    error,
    account,
    accountBalance,
    hasMetaMask,
    refresh,
    connect,
    approveBot,
    forgetWallet,
    setMode,
    practiceInfo,
    restarting,
    practice,
    addPractice,
    resetPractice,
    manualStops,
    loadStops,
    setStop,
    tradeLevels,
    buy,
    botSettings,
    loadSettings,
    setAiLeverage,
  };
}
