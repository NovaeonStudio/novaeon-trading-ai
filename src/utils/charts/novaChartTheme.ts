/**
 * One chart theme for the whole app (ECharts): brand palette, profit/loss colors, recessive grid,
 * readable axis labels and calm tooltips, selected separately for dark and light mode.
 *
 * - Every ECharts instance uses `:theme="chartTheme"` from `useNovaChartTheme()`; the registered
 *   themes ('nova-dark' / 'nova-light') style axes, grid, legend, tooltip, dataZoom and series defaults.
 * - Charts that need explicit colors (profit/loss, the single accent line, reference lines) read them
 *   from `tokens` instead of hard-coding hex values.
 *
 * Categorical palette: 8 brand-derived hues (amber, indigo, teal, violet, coral, sky, lime, magenta),
 * stepped per mode and ordered so adjacent series stay apart for color-blind readers. Validated with the
 * dataviz palette checker (adjacent CVD ΔE ≥ 14 dark / 15 light, normal-vision ΔE ≥ 21, all ≥ 3:1 on the
 * dark surface). Series take slots in this fixed order; never generate extra hues.
 */
import { registerTheme } from 'echarts/core';
import { ColorPreferences } from '@/stores/colors';

export type NovaChartMode = 'dark' | 'light';

export interface NovaChartTokens {
  mode: NovaChartMode;
  fontFamily: string;
  /** Strong ink: tooltip values, titles. */
  text: string;
  /** Axis labels, legend text. */
  textMuted: string;
  /** Axis names, quiet annotations. */
  textDim: string;
  /** Hairline grid (split lines). */
  grid: string;
  /** Axis base line. */
  axis: string;
  /** Crosshair / axis pointer. */
  pointer: string;
  /** Chart surface (used for the 2px ring around markers). */
  surface: string;
  tooltipBg: string;
  tooltipBorder: string;
  /** The one accent for single-series charts (equity, balance). */
  accent: string;
  accentArea: string;
  profit: string;
  loss: string;
  profitArea: string;
  lossArea: string;
  /** Neutral series (volume, "other", reference data). */
  neutral: string;
  neutralArea: string;
  /** Warning / "attention" (amber); pairs with an icon or label, never color alone. */
  warn: string;
  /** Secondary brand hue (indigo), e.g. a comparison line. */
  secondary: string;
  /** Ink for text set inside a colored fill (price tags on accent/profit/loss). */
  onColor: string;
  /** Unfilled meter track / empty heatmap cell: one quiet step off the surface. */
  track: string;
  categorical: string[];
}

const FONT = "Manrope, ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif";

export const NOVA_CHART_TOKENS: Record<NovaChartMode, NovaChartTokens> = {
  dark: {
    mode: 'dark',
    fontFamily: FONT,
    text: '#EDF0FB',
    textMuted: '#94A0C6',
    textDim: '#6E7899',
    grid: 'rgba(148, 160, 198, 0.09)',
    axis: 'rgba(148, 160, 198, 0.22)',
    pointer: 'rgba(148, 160, 198, 0.45)',
    surface: '#10152A',
    tooltipBg: 'rgba(21, 27, 51, 0.96)',
    tooltipBorder: '#2A3150',
    accent: '#F4B25A',
    accentArea: 'rgba(244, 178, 90, 0.10)',
    profit: '#00D492',
    loss: '#FF637E',
    profitArea: 'rgba(0, 212, 146, 0.12)',
    lossArea: 'rgba(255, 99, 126, 0.14)',
    neutral: '#4A536F',
    neutralArea: 'rgba(148, 160, 198, 0.10)',
    warn: '#F4B25A',
    secondary: '#6C7BFF',
    onColor: '#0A0E1C',
    track: '#1E2542',
    categorical: [
      '#C8830B',
      '#6572E4',
      '#00A38F',
      '#8951BF',
      '#D55948',
      '#0093C5',
      '#799A2D',
      '#C05296',
    ],
  },
  light: {
    mode: 'light',
    fontFamily: FONT,
    text: '#0F1428',
    textMuted: '#4A536F',
    textDim: '#6E7899',
    grid: 'rgba(22, 28, 51, 0.07)',
    axis: 'rgba(22, 28, 51, 0.18)',
    pointer: 'rgba(22, 28, 51, 0.35)',
    surface: '#FFFFFF',
    tooltipBg: 'rgba(255, 255, 255, 0.98)',
    tooltipBorder: '#DCE1F2',
    accent: '#C47A0A',
    accentArea: 'rgba(196, 122, 10, 0.10)',
    profit: '#009966',
    loss: '#E11D48',
    profitArea: 'rgba(0, 153, 102, 0.12)',
    lossArea: 'rgba(225, 29, 72, 0.12)',
    neutral: '#A5AED0',
    neutralArea: 'rgba(74, 83, 111, 0.08)',
    warn: '#C47A0A',
    secondary: '#4D53D9',
    onColor: '#FFFFFF',
    track: '#E6E9F4',
    categorical: [
      '#D98B09',
      '#4D53D9',
      '#009D89',
      '#7733B1',
      '#D95544',
      '#008DBE',
      '#729513',
      '#BF4392',
    ],
  },
};

export const NOVA_CHART_THEME: Record<NovaChartMode, string> = {
  dark: 'nova-dark',
  light: 'nova-light',
};

function axis(t: NovaChartTokens, showLine: boolean) {
  return {
    axisLine: { show: showLine, lineStyle: { color: t.axis, width: 1 } },
    axisTick: { show: false },
    axisLabel: { color: t.textMuted, fontSize: 11, fontFamily: t.fontFamily, margin: 10 },
    splitLine: { show: true, lineStyle: { color: t.grid, width: 1, type: 'solid' } },
    splitArea: { show: false },
    nameTextStyle: { color: t.textDim, fontSize: 11, fontFamily: t.fontFamily },
  };
}

function buildTheme(t: NovaChartTokens) {
  return {
    color: t.categorical,
    backgroundColor: 'transparent',
    textStyle: { fontFamily: t.fontFamily, color: t.textMuted },
    title: {
      left: 0,
      textStyle: { color: t.text, fontSize: 14, fontWeight: 600, fontFamily: t.fontFamily },
      subtextStyle: { color: t.textMuted, fontSize: 12, fontFamily: t.fontFamily },
    },
    legend: {
      icon: 'roundRect',
      itemWidth: 12,
      itemHeight: 4,
      itemGap: 16,
      textStyle: { color: t.textMuted, fontSize: 12, fontFamily: t.fontFamily },
      inactiveColor: t.neutral,
      pageIconColor: t.textMuted,
      pageIconInactiveColor: t.neutral,
      pageTextStyle: { color: t.textMuted },
    },
    tooltip: {
      confine: true,
      backgroundColor: t.tooltipBg,
      borderColor: t.tooltipBorder,
      borderWidth: 1,
      padding: [8, 12],
      textStyle: { color: t.text, fontSize: 12, fontFamily: t.fontFamily },
      extraCssText:
        'border-radius: 12px; box-shadow: 0 12px 32px -12px rgba(0,0,0,0.45); backdrop-filter: blur(8px);',
      axisPointer: {
        lineStyle: { color: t.pointer, width: 1, type: 'solid' },
        crossStyle: { color: t.pointer, width: 1, type: 'solid' },
        label: { backgroundColor: t.tooltipBorder, color: t.text, fontFamily: t.fontFamily },
      },
    },
    axisPointer: {
      lineStyle: { color: t.pointer, width: 1, type: 'solid' },
      crossStyle: { color: t.pointer, width: 1, type: 'solid' },
      label: { backgroundColor: t.tooltipBorder, color: t.text, fontFamily: t.fontFamily },
    },
    categoryAxis: { ...axis(t, true), splitLine: { show: false } },
    valueAxis: axis(t, false),
    logAxis: axis(t, false),
    timeAxis: { ...axis(t, true), splitLine: { show: false } },
    line: {
      lineStyle: { width: 2, cap: 'round', join: 'round' },
      symbol: 'circle',
      symbolSize: 8,
      showSymbol: false,
      smooth: false,
      itemStyle: { borderWidth: 2, borderColor: t.surface },
    },
    bar: {
      barMaxWidth: 24,
      itemStyle: { borderRadius: [4, 4, 0, 0], borderWidth: 0 },
    },
    scatter: {
      symbolSize: 10,
      itemStyle: { borderWidth: 2, borderColor: t.surface, opacity: 0.9 },
    },
    candlestick: {
      itemStyle: {
        color: t.profit,
        color0: t.loss,
        borderColor: t.profit,
        borderColor0: t.loss,
        borderWidth: 1,
      },
    },
    boxplot: {
      itemStyle: { color: t.neutralArea, borderColor: t.textMuted, borderWidth: 1.5 },
    },
    pie: { itemStyle: { borderColor: t.surface, borderWidth: 2, borderRadius: 4 } },
    gauge: {
      axisLine: { lineStyle: { color: [[1, t.grid]] } },
      axisLabel: { color: t.textMuted },
      title: { color: t.textMuted },
      detail: { color: t.text },
    },
    dataZoom: {
      backgroundColor: 'transparent',
      borderColor: t.grid,
      borderRadius: 6,
      fillerColor: t.accentArea,
      handleStyle: { color: t.surface, borderColor: t.pointer, borderWidth: 1 },
      moveHandleStyle: { color: t.axis, opacity: 1 },
      emphasis: {
        handleStyle: { borderColor: t.accent },
        moveHandleStyle: { color: t.accent },
      },
      dataBackground: {
        lineStyle: { color: t.textDim, width: 1, opacity: 0.6 },
        areaStyle: { color: t.neutralArea, opacity: 1 },
      },
      selectedDataBackground: {
        lineStyle: { color: t.accent, width: 1 },
        areaStyle: { color: t.accentArea, opacity: 1 },
      },
      brushStyle: { color: t.accentArea },
      textStyle: { color: t.textMuted, fontFamily: t.fontFamily, fontSize: 11 },
    },
    visualMap: { textStyle: { color: t.textMuted, fontFamily: t.fontFamily } },
    markPoint: { label: { color: t.text, fontFamily: t.fontFamily } },
    toolbox: {
      iconStyle: { borderColor: t.textMuted },
      emphasis: { iconStyle: { borderColor: t.accent } },
    },
  };
}

registerTheme(NOVA_CHART_THEME.dark, buildTheme(NOVA_CHART_TOKENS.dark));
registerTheme(NOVA_CHART_THEME.light, buildTheme(NOVA_CHART_TOKENS.light));

/** Escape text (pair names, strategy names from the API) before it goes into tooltip HTML. */
export function novaEscape(s: unknown): string {
  return String(s ?? '').replace(
    /[&<>"']/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c] as string,
  );
}

/** Tooltip heading line (quiet, small). */
export function novaTooltipTitle(t: NovaChartTokens, title: unknown): string {
  return `<div style="color:${t.textMuted};font-size:11px;margin-bottom:4px">${novaEscape(title)}</div>`;
}

/**
 * One tooltip row: a short line key in the series color, the value (strong), then the label (quiet).
 * Values lead, labels follow; `valueColor` is for profit/loss tinted values.
 */
export function novaTooltipRow(
  t: NovaChartTokens,
  color: string,
  label: unknown,
  value: unknown,
  valueColor?: string,
): string {
  return (
    `<div style="display:flex;align-items:center;gap:8px;line-height:20px">` +
    `<span style="display:inline-block;width:10px;height:3px;border-radius:2px;background:${color}"></span>` +
    `<span style="font-weight:600;color:${valueColor ?? t.text};font-variant-numeric:tabular-nums">${novaEscape(value)}</span>` +
    `<span style="color:${t.textMuted}">${novaEscape(label)}</span></div>`
  );
}

/** Profit/loss color for a signed value. */
export function novaPnlColor(t: NovaChartTokens, v: number | null | undefined): string {
  return (v ?? 0) >= 0 ? t.profit : t.loss;
}

/** Rounded data end for a (possibly negative) bar: 4px at the value end, square at the baseline. */
export function novaBarRadius(value: number | null | undefined, horizontal = false): number[] {
  const neg = (value ?? 0) < 0;
  if (horizontal) return neg ? [4, 0, 0, 4] : [0, 4, 4, 0];
  return neg ? [0, 0, 4, 4] : [4, 4, 0, 0];
}

/**
 * Standard plot area. ECharts 6 keeps axis labels and axis names inside the chart box by itself
 * (grid.outerBoundsMode 'auto'), so the margins here are only the breathing room around them.
 */
export function novaGrid(extra: Record<string, unknown> = {}) {
  return { left: 8, right: 16, top: 28, bottom: 8, ...extra };
}

/** Colors for price reference lines and trade markers, shared by the market chart and trade charts. */
export function novaTradeColors(t: NovaChartTokens) {
  return {
    entry: t.profit,
    exit: t.accent,
    stop: t.loss,
    liquidation: t.loss,
    now: t.accent,
    adjustment: t.secondary,
  };
}

/** Price tag label for a horizontal mark line: pill in the line color, ink picked for contrast. */
export function novaPriceTag(t: NovaChartTokens, color: string) {
  return {
    color: t.onColor,
    backgroundColor: color,
    padding: [3, 6],
    borderRadius: 4,
    fontSize: 11,
    fontWeight: 600 as const,
    fontFamily: t.fontFamily,
  };
}

/** Quiet text label on a reference line (no fill), in text tokens. */
export function novaLineLabel(t: NovaChartTokens) {
  return { color: t.textMuted, fontSize: 11, fontFamily: t.fontFamily };
}

/** Current chart theme name + tokens, following the app's dark/light setting. */
export function useNovaChartTheme() {
  const settingsStore = useSettingsStore();
  const mode = computed<NovaChartMode>(() => (settingsStore.isDarkTheme ? 'dark' : 'light'));
  const chartTheme = computed(() => NOVA_CHART_THEME[mode.value]);
  const tokens = computed(() => NOVA_CHART_TOKENS[mode.value]);
  return { mode, chartTheme, tokens };
}

/**
 * Candle up/down colors from the theme tokens, following the user's "green up / red up" preference.
 */
export function useNovaCandleColors() {
  const colorStore = useColorStore();
  const { tokens } = useNovaChartTheme();
  return computed(() => {
    const t = tokens.value;
    const redUp = colorStore.colorPreference === ColorPreferences.RED_UP;
    return { up: redUp ? t.loss : t.profit, down: redUp ? t.profit : t.loss };
  });
}
