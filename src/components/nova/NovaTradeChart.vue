<script setup lang="ts">
/**
 * Position chart for one trade, drawn like a trading terminal's position tool:
 * - readable candles on the strategy timeframe (4h / 1d built from them), range presets, drag to pan,
 *   pinch or Ctrl + scroll to zoom;
 * - average entry, break-even after fees, stop (with a live preview while it is being edited), liquidation,
 *   the strategy's exit trigger (10-candle low) and breakout level (20-candle high) as step lines;
 * - risk zone (entry → stop) and open-profit zone (entry → now), every fill, the Sentinel news check at entry;
 * - price tags on the right as HTML (stacked so they never overlap), a legend that doubles as the
 *   table view, and an "if sold at this price" readout under the pointer.
 * Layers are switchable and remembered per browser (separately for Simple and Pro).
 */
import type {
  BarSeriesOption,
  CandlestickSeriesOption,
  EChartsOption,
  LineSeriesOption,
  MarkAreaComponentOption,
  MarkLineComponentOption,
  ScatterSeriesOption,
} from 'echarts';
import type { ElementEvent } from 'echarts';
import ECharts from 'vue-echarts';
import { BarChart, CandlestickChart, LineChart, ScatterChart } from 'echarts/charts';
import {
  AxisPointerComponent,
  DataZoomComponent,
  GridComponent,
  MarkAreaComponent,
  MarkLineComponent,
  TooltipComponent,
} from 'echarts/components';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import type { ClosedTrade, Trade } from '@/types';
import type { KevRecord } from './kev';
import type { NovaTradeLevels } from '@/composables/useNovaControl';
import {
  aggregateCandles,
  breakEvenPrice,
  novaPriceText,
  positionCandles,
  profitAtPrice,
  tradeFills,
  withLiveCandle,
  type NovaCandle,
  type NovaFill,
} from '@/utils/novaPosition';
import { currentLocale } from '@/i18n';

use([
  CandlestickChart,
  LineChart,
  BarChart,
  ScatterChart,
  CanvasRenderer,
  GridComponent,
  TooltipComponent,
  AxisPointerComponent,
  MarkLineComponent,
  MarkAreaComponent,
  DataZoomComponent,
]);

const props = withDefaults(
  defineProps<{
    trade: Trade | ClosedTrade;
    /** Minimum number of strategy candles to load. */
    limit?: number;
    /** Fixed plot height (CSS). Default: responsive (about 300px on phones, 420–480px on desktop). */
    height?: string;
    /** Sentinel record of the entry (news check marker). */
    kev?: KevRecord | null;
    /** Stop price being edited: drawn as a preview line. */
    previewStop?: number | null;
    /** The current stop is a manual override. */
    manualStop?: boolean;
    /** The stop tag becomes a button that asks the parent to open the stop editor. */
    editableStop?: boolean;
    /** Engine-side levels from the control service; used instead of local estimates when present. */
    engineLevels?: NovaTradeLevels | null;
  }>(),
  {
    limit: 800,
    height: undefined,
    kev: null,
    previewStop: null,
    manualStop: false,
    editableStop: false,
    engineLevels: null,
  },
);
const emit = defineEmits<{ editStop: [] }>();

const H = 3_600_000;
const D = 24 * H;
const TF_MS: Record<string, number> = {
  '1m': 60_000,
  '5m': 300_000,
  '15m': 900_000,
  '30m': 1_800_000,
  '1h': H,
  '2h': 2 * H,
  '4h': 4 * H,
  '6h': 6 * H,
  '8h': 8 * H,
  '12h': 12 * H,
  '1d': D,
};

const botStore = useBotStore();
const { simple } = useNovaMode();
const { chartTheme, tokens } = useNovaChartTheme();
const candleColors = useNovaCandleColors();
const wide = useMediaQuery('(min-width: 640px)');

const raw = shallowRef<NovaCandle[]>([]);
const baseTfMs = ref(H);
const loading = ref(false);
const loaded = ref(false);

const { t: tr } = useI18n();
const t = computed(() => props.trade);
const currency = computed(() => botStore.activeBot.botState?.stake_currency ?? '');
const nowRate = computed(() =>
  t.value.is_open && 'current_rate' in t.value ? (t.value.current_rate ?? null) : null,
);

// ---------- Timeframe & range ----------
const baseTf = computed(() => botStore.activeBot.botState?.timeframe ?? '1h');
const tfOptions = computed(() => {
  const base = TF_MS[baseTf.value] ?? H;
  return [baseTf.value, '4h', '1d'].filter(
    (tf, i, all) =>
      all.indexOf(tf) === i && (i === 0 || ((TF_MS[tf] ?? 0) > base && TF_MS[tf]! % base === 0)),
  );
});
const tfPref = useStorage('nova-trade-chart-tf', '');
const activeTf = computed(() =>
  !simple.value && tfOptions.value.includes(tfPref.value) ? tfPref.value : tfOptions.value[0]!,
);
const tfMs = computed(() => Math.max(TF_MS[activeTf.value] ?? 0, baseTfMs.value));

type RangeKey = 'trade' | '1d' | '1w' | '1m';
const range = ref<RangeKey>('trade');
const rangeOptions = computed<{ key: RangeKey; label: string }[]>(() => [
  {
    key: 'trade',
    label: t.value.is_open
      ? simple.value
        ? tr('chart.range.sinceBought')
        : tr('chart.range.sinceEntry')
      : tr('chart.range.wholeTrade'),
  },
  { key: '1d', label: simple.value ? tr('chart.range.day') : tr('chart.range.d1') },
  { key: '1w', label: simple.value ? tr('chart.range.week') : tr('chart.range.w1') },
  { key: '1m', label: simple.value ? tr('chart.range.month') : tr('chart.range.m1') },
]);
/** Window the user panned / zoomed to (not reactive on purpose: it must not rebuild the option). */
let userWindow: [number, number] | null = null;
const zoomed = ref(false);

function setRange(r: RangeKey) {
  range.value = r;
  userWindow = null;
  zoomed.value = false;
}
function setTf(tf: string) {
  tfPref.value = tf;
  userWindow = null;
  zoomed.value = false;
}

// ---------- Data ----------
async function load() {
  const bot = botStore.activeBot;
  const timeframe = bot.botState?.timeframe;
  if (!timeframe) return;
  const ms = TF_MS[timeframe] ?? H;
  // Enough candles for the whole trade plus context before the entry (and a month for the 1M range).
  const from = props.trade.open_timestamp - 60 * ms;
  const need = Math.ceil((Date.now() - from) / ms) + 30;
  loading.value = true;
  try {
    const ph = await bot.getCandlesQuiet(
      props.trade.pair,
      timeframe,
      Math.min(Math.max(props.limit, need), 3000),
    );
    baseTfMs.value = ph?.timeframe_ms || ms;
    raw.value = positionCandles(ph);
  } finally {
    loading.value = false;
    loaded.value = true;
  }
}
watch(
  () => props.trade.trade_id,
  () => {
    raw.value = [];
    loaded.value = false;
    setRange('trade');
    load();
  },
  { immediate: true },
);
useIntervalFn(() => {
  if (props.trade.is_open) load();
}, 60_000);

const candles = computed(() => {
  let rows = withLiveCandle(raw.value, baseTfMs.value, nowRate.value);
  if (tfMs.value > baseTfMs.value) rows = aggregateCandles(rows, tfMs.value);
  return rows;
});
const bucket = (ts: number) => Math.floor(ts / tfMs.value) * tfMs.value;
const fills = computed<NovaFill[]>(() => tradeFills(t.value));
const kevTs = computed(() => {
  if (!props.kev) return null;
  const ts = Date.parse(props.kev.time);
  return Number.isFinite(ts) ? ts : t.value.open_timestamp;
});

// ---------- Layers ----------
type LayerKey =
  | 'entry'
  | 'breakeven'
  | 'stop'
  | 'liq'
  | 'exitSignal'
  | 'breakout'
  | 'zones'
  | 'fills'
  | 'ai'
  | 'volume';
const proLayers = useStorage<Record<LayerKey, boolean>>(
  'nova-trade-chart-layers-pro',
  {
    entry: true,
    breakeven: true,
    stop: true,
    liq: true,
    exitSignal: true,
    breakout: false,
    zones: true,
    fills: true,
    ai: true,
    volume: true,
  },
  localStorage,
  { mergeDefaults: true },
);
const simpleLayers = useStorage<Record<LayerKey, boolean>>(
  'nova-trade-chart-layers-simple',
  {
    entry: true,
    breakeven: false,
    stop: true,
    liq: true,
    exitSignal: true,
    breakout: false,
    zones: true,
    fills: true,
    ai: true,
    volume: false,
  },
  localStorage,
  { mergeDefaults: true },
);
const layers = computed(() => (simple.value ? simpleLayers.value : proLayers.value));
function toggleLayer(key: LayerKey, on: boolean) {
  (simple.value ? simpleLayers : proLayers).value[key] = on;
}

const tc = computed(() => novaTradeColors(tokens.value));
type Dash = 'solid' | 'dashed' | 'dotted';
const lastCandle = computed(() => candles.value[candles.value.length - 1] ?? null);
const hasLevels = computed(() => candles.value.some((c) => c.lo10 !== null));
const hasManyBuys = computed(() => fills.value.filter((f) => f.side === 'buy').length > 1);

/** Everything the Layers menu can switch, with its key for the menu and the legend. */
const layerDefs = computed(() => {
  const s = simple.value;
  const k = tokens.value;
  const c = tc.value;
  const x = t.value;
  const defs: {
    key: LayerKey;
    label: string;
    color: string;
    dash?: Dash;
    mark?: 'zone' | 'fill' | 'bar' | 'ai';
    show: boolean;
  }[] = [
    {
      key: 'entry',
      label: s
        ? tr('chart.layer.boughtAt')
        : hasManyBuys.value
          ? tr('chart.layer.averageEntry')
          : tr('chart.layer.entry'),
      color: c.entry,
      show: true,
    },
    {
      key: 'breakeven',
      label: tr('chart.layer.breakevenAfterFees'),
      color: k.textMuted,
      dash: 'dotted',
      show: x.is_open,
    },
    {
      key: 'stop',
      label: s ? tr('chart.layer.safetyStop') : tr('chart.layer.stop'),
      color: c.stop,
      dash: 'dashed',
      show: x.is_open && !!x.stop_loss_abs,
    },
    {
      key: 'liq',
      label: s ? tr('chart.layer.forcedSale') : tr('chart.layer.liquidation'),
      color: c.liquidation,
      dash: 'dotted',
      show: x.is_open && !!(props.engineLevels?.liquidation ?? x.liquidation_price),
    },
    {
      key: 'exitSignal',
      label: s ? tr('chart.layer.botSellsBelow') : tr('chart.layer.exitSignal'),
      color: k.secondary,
      show: hasLevels.value,
    },
    {
      key: 'breakout',
      label: tr('chart.layer.breakout'),
      color: k.textDim,
      show: hasLevels.value && !s,
    },
    {
      key: 'zones',
      label: s ? tr('chart.layer.zonesSimple') : tr('chart.layer.zones'),
      color: c.stop,
      mark: 'zone',
      show: true,
    },
    {
      key: 'fills',
      label: s ? tr('chart.layer.buysAndSells') : tr('chart.layer.fills'),
      color: c.entry,
      mark: 'fill',
      show: fills.value.length > 0,
    },
    {
      key: 'ai',
      label: tr('chart.layer.sentinel'),
      color: k.secondary,
      mark: 'ai',
      show: !!props.kev,
    },
    { key: 'volume', label: tr('chart.layer.volume'), color: k.neutral, mark: 'bar', show: true },
  ];
  return defs.filter((d) => d.show);
});

interface Level {
  key: string;
  name: string;
  price: number;
  color: string;
  dash: Dash;
  width?: number;
  /** Drawn by a step series (no mark line). */
  series?: boolean;
  /** Extra quiet text in the tag (distance, "manual"). */
  note?: string;
}

function distNote(price: number): string | undefined {
  const now = nowRate.value;
  if (!now || simple.value) return undefined;
  return novaPct(price / now - 1, 1, true);
}

const levels = computed<Level[]>(() => {
  const x = t.value;
  const k = tokens.value;
  const c = tc.value;
  const L = layers.value;
  const s = simple.value;
  const out: Level[] = [];
  if (L.entry)
    out.push({
      key: 'entry',
      name: s
        ? tr('chart.tag.bought')
        : hasManyBuys.value
          ? tr('chart.tag.avgEntry')
          : tr('chart.tag.entry'),
      price: x.open_rate,
      color: c.entry,
      dash: 'solid',
    });
  if (x.is_open) {
    const eng = props.engineLevels;
    const be = eng?.break_even ?? breakEvenPrice(x);
    const liq = eng?.liquidation ?? x.liquidation_price;
    if (L.breakeven && be)
      out.push({
        key: 'breakeven',
        name: tr('chart.tag.breakeven'),
        price: be,
        color: k.textMuted,
        dash: 'dotted',
      });
    if (L.stop && x.stop_loss_abs)
      out.push({
        key: 'stop',
        name: s ? tr('chart.tag.safetyStop') : tr('chart.tag.stop'),
        price: x.stop_loss_abs,
        color: c.stop,
        dash: 'dashed',
        note: props.manualStop ? tr('chart.tag.manual') : distNote(x.stop_loss_abs),
      });
    if (L.liq && liq)
      out.push({
        key: 'liq',
        name: s ? tr('chart.tag.forcedSale') : tr('chart.tag.liq'),
        price: liq,
        color: c.liquidation,
        dash: 'dotted',
        note: distNote(liq),
      });
    const last = lastCandle.value;
    const exitLevel = eng?.exit_level ?? last?.lo10;
    const entryLevel = eng?.entry_level ?? last?.hi20;
    if (L.exitSignal && exitLevel)
      out.push({
        key: 'exitSignal',
        name: s ? tr('chart.tag.sellsBelow') : tr('chart.tag.exitSignal'),
        price: exitLevel,
        color: k.secondary,
        dash: 'solid',
        series: true,
        note: distNote(exitLevel),
      });
    if (L.breakout && !s && entryLevel)
      out.push({
        key: 'breakout',
        name: tr('chart.tag.breakout'),
        price: entryLevel,
        color: k.textDim,
        dash: 'solid',
        series: true,
      });
    if (props.previewStop)
      out.push({
        key: 'preview',
        name: tr('chart.tag.newStop'),
        price: props.previewStop,
        color: c.stop,
        dash: 'solid',
        width: 2,
        note: distNote(props.previewStop),
      });
    if (nowRate.value)
      out.push({
        key: 'now',
        name: tr('chart.tag.now'),
        price: nowRate.value,
        color: c.now,
        dash: 'solid',
      });
  } else if ('close_rate' in x && x.close_rate) {
    out.push({
      key: 'exit',
      name: s ? tr('chart.tag.sold') : tr('chart.tag.exit'),
      price: x.close_rate,
      color: c.exit,
      dash: 'solid',
    });
  }
  return out;
});

// ---------- Geometry ----------
const GRID_TOP = 12;
const X_AXIS_BAND = 28;
const gridRight = computed(() => (wide.value ? 80 : 68));
const volH = computed(() => (layers.value.volume ? (wide.value ? 52 : 36) : 0));
const priceBottom = computed(() => X_AXIS_BAND + (volH.value ? volH.value + 12 : 0));

/** Visible y-range: the candles in view plus every line close to them; far lines get an edge tag. */
function yExtent(v: { min: number; max: number }) {
  const span = Math.max(v.max - v.min, Math.abs(v.max) * 0.004);
  let lo = v.min;
  let hi = v.max;
  for (const l of levels.value) {
    if (l.price >= v.min - span * 0.75 && l.price <= v.max + span * 0.75) {
      lo = Math.min(lo, l.price);
      hi = Math.max(hi, l.price);
    }
  }
  const pad = (hi - lo) * 0.08 || span * 0.1;
  return { min: lo - pad, max: hi + pad };
}

function windowFor(r: RangeKey): [number, number] | null {
  const rows = candles.value;
  if (!rows.length) return null;
  const ms = tfMs.value;
  const first = rows[0]!.ts;
  const end = rows[rows.length - 1]!.ts + 3 * ms;
  const x = t.value;
  let start: number;
  let stop = end;
  if (r === 'trade') {
    const exitTs =
      !x.is_open && 'close_timestamp' in x && x.close_timestamp ? x.close_timestamp : end;
    const dur = Math.max(exitTs - x.open_timestamp, ms);
    start = bucket(x.open_timestamp) - Math.max(20 * ms, dur * 0.4);
    if (!x.is_open) stop = Math.min(end, bucket(exitTs) + Math.max(6 * ms, dur * 0.15));
  } else start = end - (r === '1d' ? D : r === '1w' ? 7 * D : 30 * D);
  // Never fewer than ~36 candles in view, so the bodies stay readable and not blown up.
  start = Math.min(start, stop - 36 * ms);
  return [Math.max(first, start), stop];
}

// ---------- Chart option ----------
function fillLabel(f: NovaFill): string {
  const s = simple.value;
  if (f.kind === 'entry') return s ? tr('chart.tag.bought') : tr('chart.fill.buy');
  if (f.kind === 'add') return s ? tr('chart.fill.boughtMore') : tr('chart.fill.add');
  if (f.stop) return s ? tr('chart.tag.safetyStop') : tr('chart.tag.stop');
  if (f.kind === 'partial') return s ? tr('chart.fill.soldPart') : tr('chart.fill.sell');
  return s ? tr('chart.tag.sold') : tr('chart.tag.exit');
}
/** Longer wording for the tooltip. */
function fillDetail(f: NovaFill): string {
  const base = fillLabel(f);
  if (f.tag !== 'manual') return base;
  return simple.value
    ? tr('chart.fill.byYou', { label: base })
    : tr('chart.fill.manual', { label: base });
}

const option = computed((): EChartsOption | null => {
  const rows = candles.value;
  if (!rows.length) return null;
  const k = tokens.value;
  const c = tc.value;
  const { up, down } = candleColors.value;
  const L = layers.value;
  const x = t.value;
  const ms = tfMs.value;
  const s = simple.value;
  const lastTs = rows[rows.length - 1]!.ts;
  const pad = [1, 2, 3].map((i) => lastTs + i * ms);
  const rightEdge = pad[pad.length - 1]!;

  const candleData: CandlestickSeriesOption['data'] = [
    ...rows.map((r) =>
      r.live
        ? { value: [r.ts, r.o, r.c, r.l, r.h], itemStyle: { opacity: 0.6 } }
        : [r.ts, r.o, r.c, r.l, r.h],
    ),
    ...pad.map((ts) => [ts, '-', '-', '-', '-'] as (number | string)[]),
  ] as CandlestickSeriesOption['data'];

  // Horizontal lines (step-series levels are drawn by their own series).
  const markLine: MarkLineComponentOption = {
    symbol: 'none',
    silent: true,
    animation: false,
    label: { show: false },
    data: levels.value
      .filter((l) => !l.series)
      .map((l) => ({
        name: l.name,
        yAxis: l.price,
        lineStyle: {
          color: l.color,
          type: l.dash,
          width: l.width ?? 1,
          opacity: l.key === 'preview' ? 1 : 0.9,
        },
      })),
  };

  // Zones like a position tool: risk (entry → stop) and open profit (entry → now), or the closed result.
  const areas: NonNullable<MarkAreaComponentOption['data']> = [];
  if (L.zones) {
    const x0 = bucket(x.open_timestamp);
    if (x.is_open) {
      // Entry → stop: the risk, or (once the stop is above the entry) the profit already locked in.
      if (x.stop_loss_abs)
        areas.push([
          {
            xAxis: x0,
            yAxis: x.open_rate,
            itemStyle: {
              color: x.stop_loss_abs >= x.open_rate ? k.profitArea : k.lossArea,
              opacity: 0.55,
            },
          },
          { xAxis: rightEdge, yAxis: x.stop_loss_abs },
        ]);
      if (nowRate.value)
        areas.push([
          {
            xAxis: x0,
            yAxis: nowRate.value,
            itemStyle: { color: nowRate.value >= x.open_rate ? k.profitArea : k.lossArea },
          },
          { xAxis: rightEdge, yAxis: x.open_rate },
        ]);
    } else if ('close_rate' in x && x.close_rate && x.close_timestamp) {
      areas.push([
        {
          xAxis: x0,
          yAxis: x.close_rate,
          itemStyle: { color: x.close_rate >= x.open_rate ? k.profitArea : k.lossArea },
        },
        { xAxis: bucket(x.close_timestamp) + ms, yAxis: x.open_rate },
      ]);
    }
  }

  const series: (
    CandlestickSeriesOption | LineSeriesOption | ScatterSeriesOption | BarSeriesOption
  )[] = [
    {
      type: 'candlestick',
      name: 'Price',
      data: candleData,
      barMaxWidth: 14,
      barMinWidth: 1,
      itemStyle: { color: up, color0: down, borderColor: up, borderColor0: down },
      markLine,
      markArea: { silent: true, animation: false, data: areas },
      z: 3,
    },
  ];

  const step = (key: 'lo10' | 'hi20', name: string, color: string, width: number) =>
    ({
      type: 'line',
      name,
      step: 'start',
      data: rows.map((r) => [r.ts, r[key] ?? '-']),
      showSymbol: false,
      symbol: 'none',
      connectNulls: false,
      lineStyle: { color, width, opacity: 0.85 },
      itemStyle: { color },
      emphasis: { disabled: true },
      z: 2,
    }) as LineSeriesOption;
  if (L.exitSignal && hasLevels.value) series.push(step('lo10', 'Exit signal', k.secondary, 1.5));
  if (L.breakout && !s && hasLevels.value) series.push(step('hi20', 'Breakout', k.textDim, 1));

  const win = userWindow ?? windowFor(range.value);
  // Text labels next to fills only while candles are wide enough; zoomed out, the tooltip carries them.
  const fillText = wide.value && (!win || (win[1] - win[0]) / ms <= 90);
  if (L.fills && fills.value.length) {
    series.push({
      type: 'scatter',
      name: 'Fills',
      z: 5,
      data: fills.value.map((f) => ({
        value: [bucket(f.ts), f.price],
        symbol: 'triangle',
        symbolRotate: f.side === 'buy' ? 0 : 180,
        symbolSize: wide.value ? 13 : 11,
        itemStyle: {
          color: f.side === 'buy' ? c.entry : c.exit,
          borderColor: k.surface,
          borderWidth: 2,
          opacity: 1,
        },
        label: {
          show: fillText,
          position: f.side === 'buy' ? 'bottom' : 'top',
          distance: 6,
          formatter: fillLabel(f),
          color: k.text,
          fontSize: 11,
          fontFamily: k.fontFamily,
          backgroundColor: k.tooltipBg,
          borderColor: k.tooltipBorder,
          borderWidth: 1,
          padding: [2, 6],
          borderRadius: 4,
        },
      })),
    });
  }

  if (L.ai && props.kev && kevTs.value) {
    const kb = bucket(kevTs.value);
    const cand = rows.find((r) => r.ts === kb) ?? rows.find((r) => r.ts >= kb);
    if (cand)
      series.push({
        type: 'scatter',
        name: 'Sentinel news check',
        z: 6,
        data: [
          {
            value: [cand.ts, cand.h],
            symbol: 'roundRect',
            symbolSize: [24, 16],
            symbolOffset: [0, -18],
            itemStyle: { color: k.secondary, borderColor: k.surface, borderWidth: 2 },
            label: {
              show: true,
              position: 'inside',
              formatter: tr('chart.aiBadge'),
              color: '#FFFFFF',
              fontSize: 10,
              fontWeight: 700,
              fontFamily: k.fontFamily,
            },
          },
        ],
      });
  }

  const vol = volH.value > 0;
  if (vol)
    series.push({
      type: 'bar',
      name: 'Volume',
      xAxisIndex: 1,
      yAxisIndex: 1,
      barMaxWidth: 14,
      data: rows.map((r) => ({
        value: [r.ts, r.v],
        itemStyle: {
          color: r.c >= r.o ? up : down,
          opacity: 0.35,
          borderRadius: [2, 2, 0, 0],
        },
      })),
      silent: true,
    });

  const box = { left: 8, right: gridRight.value, outerBoundsMode: 'none' as const };

  return {
    animation: false,
    grid: [
      { ...box, top: GRID_TOP, bottom: priceBottom.value },
      ...(vol ? [{ ...box, height: volH.value, bottom: X_AXIS_BAND }] : []),
    ],
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross',
        label: {
          formatter: (p) =>
            p.axisDimension === 'y'
              ? priceText(Number(p.value))
              : timestampms(Number(p.value)).slice(0, 16),
        },
      },
      formatter: (params) => tooltipHtml(Array.isArray(params) ? params : [params]),
    },
    xAxis: [
      {
        type: 'time',
        gridIndex: 0,
        axisLabel: { show: !vol, hideOverlap: true },
        axisLine: { show: !vol },
        axisPointer: { label: { show: !vol } },
      },
      ...(vol
        ? [
            {
              type: 'time' as const,
              gridIndex: 1,
              axisLabel: { hideOverlap: true },
            },
          ]
        : []),
    ],
    yAxis: [
      {
        type: 'value',
        gridIndex: 0,
        position: 'right',
        scale: true,
        splitNumber: wide.value ? 6 : 4,
        min: (v) => yExtent(v).min,
        max: (v) => yExtent(v).max,
        // Labels are drawn in the HTML overlay, so they can make room for the price tags.
        axisLabel: { show: false },
      },
      ...(vol
        ? [
            {
              type: 'value' as const,
              gridIndex: 1,
              position: 'right' as const,
              scale: false,
              splitNumber: 1,
              axisLabel: { show: false },
              splitLine: { show: false },
              axisPointer: { show: false },
            },
          ]
        : []),
    ],
    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: vol ? [0, 1] : [0],
        filterMode: 'filter',
        ...(win ? { startValue: win[0], endValue: win[1] } : {}),
        minValueSpan: 12 * ms,
        zoomOnMouseWheel: 'ctrl',
        moveOnMouseWheel: 'shift',
        moveOnMouseMove: true,
      },
    ],
    series,
  } as EChartsOption;
});

// ---------- Tooltip ----------
interface AxisParam {
  seriesName?: string;
  value?: unknown;
  axisValue?: unknown;
}
function tooltipHtml(params: AxisParam[]): string {
  const k = tokens.value;
  const p = params.find((x) => x.seriesName === 'Price');
  const v = (p?.value ?? []) as (number | string)[];
  const ts = Number(v[0] ?? params[0]?.axisValue);
  if (!Number.isFinite(ts) || typeof v[1] !== 'number') return '';
  const [, o, cl, lo, hi] = v as number[];
  const { up, down } = candleColors.value;
  const color = (cl ?? 0) >= (o ?? 0) ? up : down;
  let html = novaTooltipTitle(k, timestampms(ts).slice(0, 16));
  if (simple.value)
    html += novaTooltipRow(k, color, tr('chart.tooltip.priceAtClose'), priceText(cl));
  else
    html +=
      novaTooltipRow(k, color, tr('chart.tooltip.open'), priceText(o)) +
      novaTooltipRow(k, color, tr('chart.tooltip.high'), priceText(hi)) +
      novaTooltipRow(k, color, tr('chart.tooltip.low'), priceText(lo)) +
      novaTooltipRow(k, color, tr('chart.tooltip.close'), priceText(cl));
  const cand = candles.value.find((r) => r.ts === ts);
  if (cand?.lo10 && layers.value.exitSignal)
    html += novaTooltipRow(
      k,
      k.secondary,
      simple.value ? tr('chart.tooltip.botSellsBelow') : tr('chart.tooltip.exitSignal'),
      priceText(cand.lo10),
    );
  if (cand?.live)
    html += `<div style="color:${k.textMuted};font-size:11px;margin-top:2px">${novaEscape(tr('chart.tooltip.forming'))}</div>`;
  const inBucket = fills.value.filter((f) => bucket(f.ts) === ts);
  for (const f of inBucket) {
    const col = f.side === 'buy' ? tc.value.entry : tc.value.exit;
    html += novaTooltipRow(
      k,
      col,
      tr('chart.tooltip.fill', {
        // Tooltip labels are lower case; German nouns keep their capital letter.
        what: currentLocale() === 'de' ? fillDetail(f) : fillDetail(f).toLowerCase(),
        amount: novaNum(f.amount, 4),
        cost: novaMoney(f.cost, currency.value, 2),
      }),
      priceText(f.price),
    );
  }
  if (props.kev && kevTs.value && bucket(kevTs.value) === ts && layers.value.ai) {
    const kv = props.kev;
    html += novaTooltipRow(
      k,
      k.secondary,
      tr('chart.tooltip.sentinel', kv.headlines ?? 0),
      kv.decision === 'veto'
        ? tr('chart.tooltip.vetoed', { lev: kv.leverage ?? 1 })
        : tr('chart.tooltip.allowed', { lev: kv.leverage ?? 1 }),
    );
  }
  return html;
}
function priceText(v: number | undefined) {
  return novaPriceText(v ?? null);
}

// ---------- Overlay: price tags, readout ----------
const chartEl = useTemplateRef<InstanceType<typeof ECharts>>('chartEl');
interface Tag extends Level {
  y: number;
  lineY: number;
  off: 'up' | 'down' | null;
}
const tags = shallowRef<Tag[]>([]);
/** Price-axis labels (the chart's own ticks), minus the ones a price tag would cover. */
const axisLabels = shallowRef<{ v: number; y: number }[]>([]);
type AxisModel = {
  getModel(): {
    getComponent(
      type: string,
      i: number,
    ): { axis?: { scale: { getTicks(): { value: number }[] } } } | undefined;
  };
};
const plotRight = ref(0);
const plotBottom = ref(0);
const TAG_GAP = 22;

/** The chart's own price ticks (internal model API; empty if it is not available). */
function axisTicks(chart: unknown): number[] {
  try {
    return (
      (chart as AxisModel)
        .getModel()
        .getComponent('yAxis', 0)
        ?.axis?.scale.getTicks()
        .map((x) => x.value) ?? []
    );
  } catch {
    return [];
  }
}

function layoutTags() {
  const ch = chartEl.value;
  if (!ch?.chart || !option.value) return;
  const height = ch.getHeight();
  plotRight.value = ch.getWidth() - gridRight.value;
  const top = GRID_TOP + 2;
  const bottom = height - priceBottom.value - 2;
  plotBottom.value = bottom;
  // Before the first render the chart has no model yet: nothing to measure.
  const px = (price: number) => {
    try {
      return Number(ch.convertToPixel({ yAxisIndex: 0 }, price));
    } catch {
      return NaN;
    }
  };
  if (!Number.isFinite(px(levels.value[0]?.price ?? 0))) return;
  const items: Tag[] = levels.value.map((l) => {
    const y = px(l.price);
    const off = !Number.isFinite(y) ? 'down' : y < top ? 'up' : y > bottom ? 'down' : null;
    const clamped = Number.isFinite(y) ? Math.min(Math.max(y, top), bottom) : bottom;
    return { ...l, lineY: clamped, y: clamped, off };
  });
  items.sort((a, b) => a.y - b.y);
  for (let i = 1; i < items.length; i++)
    items[i]!.y = Math.max(items[i]!.y, items[i - 1]!.y + TAG_GAP);
  const last = items[items.length - 1];
  if (last && last.y > bottom) {
    last.y = bottom;
    for (let i = items.length - 2; i >= 0; i--)
      items[i]!.y = Math.min(items[i]!.y, items[i + 1]!.y - TAG_GAP);
  }
  const key = (xs: Tag[]) =>
    xs.map((x) => `${x.key}:${Math.round(x.y)}:${x.price}:${x.off}`).join('|');
  if (key(items) !== key(tags.value)) tags.value = items;
  const labels = axisTicks(ch.chart)
    .map((v) => ({ v, y: px(v) }))
    .filter(
      (l) => l.y > top + 6 && l.y < bottom - 6 && items.every((g) => Math.abs(g.y - l.y) > 17),
    );
  if (
    labels.map((l) => `${l.v}:${Math.round(l.y)}`).join() !==
    axisLabels.value.map((l) => `${l.v}:${Math.round(l.y)}`).join()
  )
    axisLabels.value = labels;
}
watch([levels, option], () => nextTick(layoutTags));
useResizeObserver(
  () => chartEl.value?.$el as HTMLElement | undefined,
  () => nextTick(layoutTags),
);

function onDataZoom() {
  const dz = (
    chartEl.value?.getOption()?.dataZoom as { startValue?: number; endValue?: number }[]
  )?.[0];
  if (dz?.startValue !== undefined && dz.endValue !== undefined) {
    userWindow = [dz.startValue, dz.endValue];
    zoomed.value = true;
  }
  layoutTags();
}
function resetZoom() {
  setRange(range.value);
  // The option does not depend on the zoom state, so push the window directly.
  const win = windowFor(range.value);
  if (win)
    chartEl.value?.dispatchAction({ type: 'dataZoom', startValue: win[0], endValue: win[1] });
}
/** "If sold at this price" under the pointer. */
const readout = ref<{ price: number; y: number } | null>(null);
function onMove(e: ElementEvent) {
  const ch = chartEl.value;
  if (!ch?.chart) return;
  const inside =
    e.offsetX > 8 &&
    e.offsetX < plotRight.value &&
    e.offsetY > GRID_TOP &&
    e.offsetY < plotBottom.value;
  if (!inside) {
    readout.value = null;
    return;
  }
  const price = Number(ch.convertFromPixel({ yAxisIndex: 0 }, e.offsetY));
  readout.value = Number.isFinite(price) ? { price, y: e.offsetY } : null;
}
const readoutText = computed(() => {
  const r = readout.value;
  if (!r) return null;
  const x = t.value;
  const p = priceText(r.price);
  if (!x.is_open) {
    const pct = novaPct(r.price / x.open_rate - 1, 1, true);
    return simple.value
      ? tr('chart.readout.closedSimple', { price: p, pct })
      : tr('chart.readout.closedPro', { price: p, pct });
  }
  const res = profitAtPrice(x, r.price);
  const money = novaMoney(res.abs, currency.value, 2, true);
  return simple.value
    ? tr('chart.readout.openSimple', { price: p, money, pct: novaPct(res.ratio, 1, true) })
    : tr('chart.readout.openPro', { price: p, money, pct: novaPct(res.ratio, 2, true) });
});
const readoutUp = computed(() => {
  const r = readout.value;
  return r ? profitAtPrice(t.value, r.price).abs >= 0 : true;
});

// ---------- Legend (doubles as the table view) ----------
const legend = computed(() => {
  const x = t.value;
  const s = simple.value;
  const cur = currency.value;
  const out: {
    key: string;
    label: string;
    value: string;
    color: string;
    dash?: Dash;
    mark?: string;
  }[] = [];
  for (const l of levels.value) {
    if (l.key === 'now' || l.key === 'exit') continue;
    let value = priceText(l.price);
    if (x.is_open && ['stop', 'preview', 'liq', 'exitSignal'].includes(l.key)) {
      const res = profitAtPrice(x, l.price);
      const money = novaMoney(res.abs, cur, 2, true);
      value = s ? tr('chart.legend.ifSoldThere', { price: value, money }) : `${value} · ${money}`;
    }
    const def = layerDefs.value.find((d) => d.key === l.key);
    out.push({
      key: l.key,
      label: l.key === 'preview' ? tr('chart.tag.newStop') : (def?.label ?? l.name),
      value,
      color: l.color,
      dash: l.dash,
    });
  }
  // Closed trades: the step line still explains the exit; name its level at the exit candle.
  if (!x.is_open && layers.value.exitSignal && hasLevels.value) {
    const exitTs = 'close_timestamp' in x && x.close_timestamp ? bucket(x.close_timestamp) : null;
    const at = candles.value.find((r) => r.ts === exitTs);
    out.push({
      key: 'exitSignal',
      label: s ? tr('chart.layer.botSellsBelow') : tr('chart.layer.exitSignal'),
      value: at?.lo10 ? tr('chart.legend.atExit', { price: priceText(at.lo10) }) : '–',
      color: tokens.value.secondary,
      dash: 'solid',
    });
  }
  if (layers.value.fills && fills.value.length)
    out.push({
      key: 'fills',
      label: s ? tr('chart.layer.buysAndSells') : tr('chart.legend.fills'),
      value: `${fills.value.length}`,
      color: tc.value.entry,
      mark: 'fill',
    });
  return out;
});

/** Line names sit next to the price axis; on phones on the left edge, so they do not hide the newest candles. */
const nameStyle = computed(() =>
  wide.value ? { right: `${gridRight.value + 4}px` } : { left: '12px' },
);
const plotStyle = computed(() => (props.height ? { height: props.height } : undefined));
</script>

<template>
  <div class="flex flex-col gap-3">
    <!-- Toolbar: candle size, range, zoom reset, layers -->
    <div class="flex flex-wrap items-center gap-2">
      <div
        v-if="!simple && tfOptions.length > 1"
        class="nova-seg text-xs"
        role="group"
        :aria-label="tr('chart.toolbar.candleSize')"
      >
        <button
          v-for="tf in tfOptions"
          :key="tf"
          type="button"
          class="nova-num max-sm:min-h-10"
          :aria-pressed="activeTf === tf"
          :title="tf === tfOptions[0] ? tr('chart.toolbar.strategyTf') : undefined"
          @click="setTf(tf)"
        >
          {{ tf }}
        </button>
      </div>
      <div class="nova-seg text-xs" role="group" :aria-label="tr('chart.toolbar.timeRange')">
        <button
          v-for="r in rangeOptions"
          :key="r.key"
          type="button"
          class="max-sm:min-h-10"
          :aria-pressed="range === r.key && !zoomed"
          @click="setRange(r.key)"
        >
          {{ r.label }}
        </button>
      </div>
      <div class="ms-auto flex items-center gap-2">
        <UButton
          v-if="zoomed"
          size="sm"
          color="neutral"
          variant="ghost"
          icon="i-mdi-fit-to-screen-outline"
          class="max-sm:min-h-10"
          @click="resetZoom"
          >{{ tr('chart.toolbar.resetView') }}</UButton
        >
        <UPopover :content="{ align: 'end', side: 'bottom', sideOffset: 6 }">
          <UButton
            size="sm"
            color="neutral"
            variant="outline"
            icon="i-mdi-layers-outline"
            class="max-sm:min-h-10"
            >{{ tr('chart.toolbar.layers') }}</UButton
          >
          <template #content>
            <div
              class="flex w-80 max-w-[calc(100vw-2rem)] flex-col gap-1 p-3"
              data-testid="nova-chart-layers"
            >
              <p class="nova-label px-1 pb-1">{{ tr('chart.toolbar.showOnChart') }}</p>
              <label
                v-for="d in layerDefs"
                :key="d.key"
                class="flex cursor-pointer items-center gap-3 rounded-lg px-1 py-1.5 text-sm text-default hover:bg-accented/60"
              >
                <UCheckbox
                  :model-value="layers[d.key]"
                  @update:model-value="(v) => toggleLayer(d.key, v === true)"
                />
                <span class="min-w-0 flex-1 text-pretty">{{ d.label }}</span>
                <span
                  v-if="d.mark === 'zone'"
                  class="h-3 w-4 rounded-sm"
                  :style="{
                    background: tokens.lossArea,
                    boxShadow: `inset 0 -6px 0 ${tokens.profitArea}`,
                  }"
                />
                <span
                  v-else-if="d.mark === 'fill'"
                  class="text-xs leading-none"
                  :style="{ color: tc.entry }"
                  aria-hidden="true"
                  >▲<span :style="{ color: tc.exit }">▼</span></span
                >
                <span
                  v-else-if="d.mark === 'ai'"
                  class="rounded px-1 text-xs font-semibold text-white"
                  :style="{ background: tokens.secondary }"
                  >{{ tr('chart.aiBadge') }}</span
                >
                <span
                  v-else-if="d.mark === 'bar'"
                  class="flex h-3 items-end gap-px"
                  aria-hidden="true"
                >
                  <span class="h-1.5 w-1 rounded-t-sm" :style="{ background: d.color }" />
                  <span class="h-3 w-1 rounded-t-sm" :style="{ background: d.color }" />
                  <span class="h-2 w-1 rounded-t-sm" :style="{ background: d.color }" />
                </span>
                <span
                  v-else
                  class="w-4 border-t-2"
                  :style="{ borderColor: d.color, borderTopStyle: d.dash ?? 'solid' }"
                  aria-hidden="true"
                />
              </label>
            </div>
          </template>
        </UPopover>
      </div>
    </div>

    <!-- Plot -->
    <div
      class="relative"
      :class="height ? '' : 'h-[23rem] sm:h-[30rem] xl:h-[34rem]'"
      :style="plotStyle"
    >
      <USkeleton v-if="!option && !loaded" class="h-full w-full rounded-xl" />
      <div
        v-else-if="!option"
        class="flex h-full flex-col items-center justify-center gap-3 text-center"
      >
        <span class="flex size-10 items-center justify-center rounded-full bg-accented">
          <UIcon name="i-mdi-chart-box-outline" class="size-5 text-muted" />
        </span>
        <p class="text-sm text-pretty text-muted">{{ tr('chart.empty') }}</p>
      </div>
      <template v-else>
        <ECharts
          ref="chartEl"
          :option="option"
          :theme="chartTheme"
          :update-options="{ notMerge: true }"
          autoresize
          class="h-full w-full transition-opacity duration-300 ease-[cubic-bezier(0.32,0.72,0,1)]"
          :class="{ 'opacity-60': loading }"
          @finished="layoutTags"
          @datazoom="onDataZoom"
          @zr:mousemove="onMove"
          @zr:globalout="readout = null"
        />
        <!-- Price tags (HTML, stacked so they never overlap) -->
        <div class="pointer-events-none absolute inset-0" aria-hidden="false">
          <svg class="absolute inset-0 h-full w-full overflow-visible">
            <line
              v-for="tg in tags.filter((x) => !x.off && Math.abs(x.y - x.lineY) > 2)"
              :key="`l-${tg.key}`"
              :x1="plotRight"
              :y1="tg.lineY"
              :x2="plotRight + 6"
              :y2="tg.y"
              :stroke="tg.color"
              stroke-width="1"
            />
          </svg>
          <span
            v-for="l in axisLabels"
            :key="`a-${l.v}`"
            class="nova-num absolute text-xs text-muted"
            :style="{ top: `${l.y - 8}px`, left: `${plotRight + 10}px` }"
            >{{ priceText(l.v) }}</span
          >
          <div
            v-for="tg in tags"
            :key="tg.key"
            class="absolute flex h-5 items-center"
            :style="{ top: `${tg.y - 10}px`, left: '0px', right: '0px' }"
          >
            <button
              v-if="tg.key === 'stop' && editableStop"
              type="button"
              class="pointer-events-auto absolute flex h-5 items-center gap-1 rounded-md border border-default/70 bg-default/90 px-1.5 text-xs font-medium whitespace-nowrap text-default shadow-sm transition duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] hover:bg-accented focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-400/60 active:scale-[0.98]"
              :style="nameStyle"
              :title="simple ? tr('stop.title.simple') : tr('stop.title.pro')"
              @click="emit('editStop')"
            >
              <UIcon name="i-mdi-pencil-outline" class="size-3.5 text-muted" />
              {{ tg.name }}<span v-if="tg.note" class="nova-num text-muted">{{ tg.note }}</span>
            </button>
            <span
              v-else
              class="absolute flex h-5 items-center gap-1 rounded-md bg-default/80 px-1.5 text-xs font-medium whitespace-nowrap text-default"
              :style="nameStyle"
            >
              {{ tg.name }}<span v-if="tg.note" class="nova-num text-muted">{{ tg.note }}</span>
            </span>
            <span
              class="nova-num absolute flex h-5 items-center gap-0.5 rounded-md px-1.5 text-xs font-semibold whitespace-nowrap"
              :style="{
                left: `${plotRight + 6}px`,
                background: tg.color,
                color: tokens.onColor,
                outline: tg.key === 'preview' ? `2px solid ${tokens.surface}` : undefined,
              }"
            >
              <UIcon v-if="tg.off === 'up'" name="i-mdi-arrow-up" class="size-3" />
              <UIcon v-else-if="tg.off === 'down'" name="i-mdi-arrow-down" class="size-3" />
              {{ priceText(tg.price) }}
            </span>
          </div>
          <!-- "If sold at this price" readout -->
          <div
            v-if="readoutText"
            class="nova-num nova-money absolute top-3 left-3 rounded-lg border border-default/70 bg-default/90 px-2 py-1 text-xs font-semibold shadow-sm"
            :class="t.is_open ? (readoutUp ? 'text-emerald-400' : 'text-rose-400') : 'text-default'"
          >
            {{ readoutText }}
          </div>
        </div>
      </template>
    </div>

    <!-- Legend: every drawn level with its value (and what selling there would give) -->
    <div
      v-if="option"
      class="nova-num flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted"
    >
      <span v-for="l in legend" :key="l.key" class="inline-flex items-center gap-2">
        <span
          v-if="l.mark === 'fill'"
          class="leading-none"
          :style="{ color: tc.entry }"
          aria-hidden="true"
          >▲<span :style="{ color: tc.exit }">▼</span></span
        >
        <span
          v-else
          class="w-3 shrink-0 border-t-2"
          :style="{ borderColor: l.color, borderTopStyle: l.dash ?? 'solid' }"
          aria-hidden="true"
        />
        <span class="text-pretty"
          >{{ l.label }} <span class="nova-money text-default">{{ l.value }}</span></span
        >
      </span>
      <span v-if="!simple && wide" class="ms-auto text-dimmed">{{ tr('chart.hint') }}</span>
    </div>
  </div>
</template>
