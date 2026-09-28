<script setup lang="ts">
import { currentLocale, intlLocale } from '@/i18n';
import type { MarkLineComponentOption } from 'echarts';
import type { ChartSliderPosition, IndicatorConfig, PairHistory, PlotConfig, Trade } from '@/types';
import { ChartType } from '@/types';

import ECharts from 'vue-echarts';

import type { EChartsOption, ScatterSeriesOption } from 'echarts';
import { BarChart, CandlestickChart, LineChart, ScatterChart } from 'echarts/charts';
import {
  AxisPointerComponent,
  CalendarComponent,
  DataZoomComponent,
  DatasetComponent,
  GridComponent,
  LegendComponent,
  TimelineComponent,
  TitleComponent,
  ToolboxComponent,
  TooltipComponent,
  VisualMapComponent,
  VisualMapPiecewiseComponent,
  MarkAreaComponent,
  MarkLineComponent,
  MarkPointComponent,
  GraphicComponent,
} from 'echarts/components';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';

use([
  AxisPointerComponent,
  CalendarComponent,
  DatasetComponent,
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  TimelineComponent,
  TitleComponent,
  ToolboxComponent,
  TooltipComponent,
  VisualMapComponent,
  VisualMapPiecewiseComponent,
  MarkAreaComponent,
  MarkLineComponent,
  MarkPointComponent,

  CandlestickChart,
  BarChart,
  LineChart,
  ScatterChart,
  CanvasRenderer,
  GraphicComponent,
]);

const props = defineProps<{
  trades: Trade[];
  dataset: PairHistory;
  heikinAshi: boolean;
  showMarkArea: boolean;
  useUTC: boolean;
  plotConfig: PlotConfig;
  theme: 'dark' | 'light';
  sliderPosition?: ChartSliderPosition;
  colorUp: string;
  colorDown: string;
  labelSide: 'left' | 'right';
  startCandleCount: number;
}>();

// `t` is the chart theme tokens below, so the translate function is `tr`.
const { t: tr } = useI18n();

/** Theme tokens for the mode the container asks for ('dark' | 'light'). */
const tokens = computed(() => NOVA_CHART_TOKENS[props.theme] ?? NOVA_CHART_TOKENS.dark);
const echartsTheme = computed(() => NOVA_CHART_THEME[props.theme] ?? NOVA_CHART_THEME.dark);

/** Readable price: ~6 significant digits, thousands separators, no float noise. */
function priceText(v: number): string {
  return Number(v.toPrecision(6)).toLocaleString(intlLocale(), { maximumFractionDigits: 8 });
}

function novaPriceLines(colClose: number): MarkLineComponentOption {
  const t = tokens.value;
  const tc = novaTradeColors(t);
  const rows = props.dataset?.data ?? [];
  const last = rows[rows.length - 1]?.[colClose];
  const lines: NonNullable<MarkLineComponentOption['data']> = [];
  for (const trade of props.trades ?? []) {
    if (!trade.is_open || trade.pair !== props.dataset?.pair) continue;
    lines.push({
      name: 'Entry',
      yAxis: trade.open_rate,
      lineStyle: { color: tc.entry, type: 'solid', width: 1, opacity: 0.8 },
      label: {
        formatter: tr('candle.lines.entry', { price: priceText(trade.open_rate) }),
        position: 'insideEndTop',
        ...novaLineLabel(t),
      },
    });
    if (trade.stop_loss_abs)
      lines.push({
        name: 'Stop',
        yAxis: trade.stop_loss_abs,
        lineStyle: { color: tc.stop, type: 'dashed', width: 1 },
        label: {
          formatter: tr('candle.lines.stop', { price: priceText(trade.stop_loss_abs) }),
          position: 'insideEndBottom',
          ...novaLineLabel(t),
        },
      });
  }
  if (typeof last === 'number') {
    // Live price: accent line with a price tag on the price-axis side.
    lines.push({
      name: 'Now',
      yAxis: last,
      lineStyle: { color: tc.now, type: 'solid', width: 1, opacity: 0.7 },
      label: {
        formatter: priceText(last),
        position: isLabelLeft.value ? 'start' : 'end',
        distance: 6,
        ...novaPriceTag(t, tc.now),
      },
    });
  }
  return {
    symbol: 'none',
    silent: true,
    animation: false,
    data: lines,
  };
}

const isLabelLeft = computed(() => props.labelSide === 'left');
// Chart default options: fixed pixel margins so every stacked pane shares the same time extent.
const LABEL_MARGIN = 76;
const EDGE_MARGIN = 12;
const MARGINLEFT = isLabelLeft.value ? LABEL_MARGIN : EDGE_MARGIN;
const MARGINRIGHT = isLabelLeft.value ? EDGE_MARGIN : LABEL_MARGIN;
const NAMEGAP = 60;
const SUBPLOTHEIGHT = 8; // Value in %
// minimal helpers for debugging
const showAxisLine = false;

const candleChart = useTemplateRef<InstanceType<typeof ECharts>>('candleChart');
const chartOptions = shallowRef<EChartsOption>({});

const strategy = computed(() => {
  return props.dataset ? props.dataset.strategy : '';
});

const pair = computed(() => {
  return props.dataset ? props.dataset.pair : '';
});

const timeframe = computed(() => {
  return props.dataset ? props.dataset.timeframe : '';
});

const hasData = computed(() => {
  return props.dataset !== null && typeof props.dataset === 'object';
});

const filteredTrades = computed(() => {
  return props.trades.filter((item: Trade) => item.pair === pair.value);
});

const chartTitle = computed(() => {
  return `${strategy.value} - ${pair.value} - ${timeframe.value}`;
});

const diffCols = computed(() => {
  return getDiffColumnsFromPlotConfig(props.plotConfig);
});

usePercentageTool(
  candleChart,
  toRef(() => props.theme),
  toRef(() => props.dataset.timeframe_ms),
);

const { formatCandleTooltip } = useCandleChartTooltip(chartOptions);

/** Candle tooltip in the Nova theme style: quiet section titles, strong values, no underlines. */
function formatNovaCandleTooltip(params: Parameters<typeof formatCandleTooltip>[0]): string {
  const t = tokens.value;
  return formatCandleTooltip(params)
    .replace(
      'font-size:13px;line-height:1.45;',
      `font-size:12px;line-height:1.6;min-width:160px;font-variant-numeric:tabular-nums;`,
    )
    .replaceAll(
      'font-weight:700; text-decoration:underline; text-align:left;',
      `font-weight:500;color:${t.textMuted};text-align:left;`,
    )
    .replace('font-weight:700; text-decoration:underline;', `font-weight:500;color:${t.textMuted};`)
    .replaceAll(
      'font-weight:700;text-align:right;',
      `font-weight:600;color:${t.text};text-align:right;`,
    );
}

function addLegend(name: string, position: number | undefined = undefined) {
  if (
    !chartOptions.value.legend ||
    Array.isArray(chartOptions.value.legend) ||
    !Array.isArray(chartOptions.value.legend.data)
  )
    return;
  if (!chartOptions.value.legend.data.includes(name)) {
    if (position !== undefined) {
      chartOptions.value.legend.data.splice(position, 0, name);
    } else {
      chartOptions.value.legend.data.push(name);
    }
  }
}

function updateChart(initial = false) {
  if (!hasData.value) {
    return;
  }
  if (chartOptions.value?.title) {
    chartOptions.value.title[0].text = chartTitle.value;
  }
  // Avoid mutation of dataset.columns array
  const columns = props.dataset.columns.slice();

  const colDate = columns.findIndex((el) => el === '__date_ts');
  const colOpen = columns.findIndex((el) => el === 'open');
  const colHigh = columns.findIndex((el) => el === 'high');
  const colLow = columns.findIndex((el) => el === 'low');
  const colClose = columns.findIndex((el) => el === 'close');
  const colVolume = columns.findIndex((el) => el === 'volume');
  const colEnterTag = columns.findIndex((el) => el === 'enter_tag');
  const colExitTag = columns.findIndex((el) => el === 'exit_tag');

  const colEntryData = columns.findIndex(
    (el) => el === '_buy_signal_close' || el === '_enter_long_signal_close',
  );
  const colExitData = columns.findIndex(
    (el) => el === '_sell_signal_close' || el === '_exit_long_signal_close',
  );

  const colShortEntryData = columns.findIndex((el) => el === '_enter_short_signal_close');
  const colShortExitData = columns.findIndex((el) => el === '_exit_short_signal_close');

  const subplotCount =
    'subplots' in props.plotConfig ? Object.keys(props.plotConfig.subplots).length + 1 : 1;

  if (Array.isArray(chartOptions.value?.dataZoom)) {
    // Only set zoom once ...
    if (initial) {
      // Add 2 candles to the initial zoom to allow for a "scroll past" effect
      const startingZoom = (1 - (props.startCandleCount + 2) / props.dataset.length) * 100;
      chartOptions.value.dataZoom.forEach((el, i) => {
        if (chartOptions.value && chartOptions.value.dataZoom) {
          chartOptions.value.dataZoom[i].start = startingZoom;
        }
      });
    } else {
      // Remove start/end settings after chart initialization to avoid chart resetting
      chartOptions.value.dataZoom.forEach((el, i) => {
        if (chartOptions.value && chartOptions.value.dataZoom) {
          delete chartOptions.value.dataZoom[i].start;
          delete chartOptions.value.dataZoom[i].end;
        }
      });
    }
  }
  let dataset = props.heikinAshi
    ? heikinAshiDataset(columns, props.dataset.data)
    : props.dataset.data.slice();

  diffCols.value.forEach(([colFrom, colTo]) => {
    if (colFrom && colTo) {
      // Enhance dataset with diff columns for area plots
      dataset = calculateDiff(columns, dataset, colFrom, colTo);
    }
  });
  // Add new rows to end to allow slight "scroll past"
  const scrollPastLength = 5;
  const lastColDate = dataset[dataset.length - 1]?.[colDate];
  if (lastColDate) {
    const newArray = Array(scrollPastLength);
    newArray[colDate] = lastColDate + props.dataset.timeframe_ms * scrollPastLength;
    dataset.push(newArray);
  }

  const t = tokens.value;
  const tc = novaTradeColors(t);
  const nameEntry = tr('candle.series.entry');
  const nameExit = tr('candle.series.exit');
  const options: EChartsOption = {
    dataset: {
      source: dataset,
    },
    grid: [
      {
        left: MARGINLEFT,
        right: MARGINRIGHT,
        top: 64,
        outerBoundsMode: 'none',
        // Grid Layout from bottom to top
        bottom: `${subplotCount * SUBPLOTHEIGHT + 2}%`,
      },
      {
        // Volume
        left: MARGINLEFT,
        right: MARGINRIGHT,
        outerBoundsMode: 'none',
        // Grid Layout from bottom to top
        bottom: `${subplotCount * SUBPLOTHEIGHT}%`,
        height: `${SUBPLOTHEIGHT}%`,
      },
    ],

    series: [
      {
        name: tr('candle.series.candles'),
        type: 'candlestick',
        barWidth: '70%',
        barMaxWidth: 16,
        itemStyle: {
          color: props.colorUp,
          color0: props.colorDown,
          borderColor: props.colorUp,
          borderColor0: props.colorDown,
          borderWidth: 1,
        },
        encode: {
          x: colDate,
          // open, close, low, high
          y: [colOpen, colClose, colLow, colHigh],
        },
        // NovaeonTradingAI: live price line + entry/stop lines of open positions on this pair
        markLine: novaPriceLines(colClose),
      },
      {
        name: tr('candle.series.volume'),
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        itemStyle: {
          color: t.neutral,
          opacity: 0.55,
          borderRadius: 0,
        },
        barMaxWidth: 16,
        large: true,
        encode: {
          x: colDate,
          y: colVolume,
        },
      },
    ],
    xAxis: [
      {
        type: 'time',
        axisLine: { onZero: false },
        axisLabel: { show: true, hideOverlap: true },
        axisPointer: {
          label: { show: false },
        },
        position: 'top',
        splitLine: { show: false },
        splitNumber: 12,
        min: 'dataMin',
        max: 'dataMax',
      },
      {
        type: 'time',
        gridIndex: 1,
        axisLine: { onZero: false },
        axisTick: { show: false },
        axisLabel: { show: false },
        axisPointer: {
          label: { show: false },
        },
        splitLine: { show: false },
        splitNumber: 20,
        min: 'dataMin',
        max: 'dataMax',
      },
    ],
    yAxis: [
      {
        scale: true,
        max: (value) => {
          return formatDecimal(value.max + (value.max - value.min) * 0.02, 'en-EN');
        },
        min: (value) => {
          return formatDecimal(value.min - (value.max - value.min) * 0.04, 'en-EN');
        },
        name: ' ', // Necessary to avoid layout shift
        nameLocation: 'middle',
        nameGap: NAMEGAP,
        axisLine: { show: showAxisLine },
        axisLabel: {
          hideOverlap: true,
          overflow: 'truncate',
          width: LABEL_MARGIN - 14,
          // The padded data min / max would crowd the rounded ticks next to them.
          showMinLabel: false,
          showMaxLabel: false,
          formatter: (v: number) => priceText(v),
        },
        position: props.labelSide,
      },
      {
        scale: true,
        gridIndex: 1,
        splitNumber: 2,
        name: tr('candle.series.volume'),
        nameLocation: 'middle',
        position: props.labelSide,
        nameGap: NAMEGAP,
        axisLabel: { show: false },
        axisLine: { show: showAxisLine },
        axisTick: { show: false },
        splitLine: { show: false },
      },
    ],
  };

  if (Array.isArray(options.series)) {
    const areaSeries = generateMarkAreaSeries(
      props.dataset,
      props.showMarkArea,
      props.plotConfig.options?.markAreaZIndex,
    );

    if (areaSeries) {
      options.series.push(areaSeries);
    }
    const signalConfigs = [
      {
        colData: colEntryData,
        name: nameEntry,
        symbol: 'triangle',
        symbolSize: 11,
        color: tc.entry,
        tooltipPrefix: tr('candle.signal.longEntry'),
        colTooltip: colEnterTag,
      },
      {
        colData: colExitData,
        name: nameExit,
        symbol: 'diamond',
        symbolSize: 11,
        color: tc.exit,
        tooltipPrefix: tr('candle.signal.longExit'),
        colTooltip: colExitTag,
      },
      {
        colData: colShortEntryData,
        name: nameEntry,
        symbol: 'triangle',
        symbolSize: 11,
        symbolRotate: 180,
        color: tc.entry,
        tooltipPrefix: tr('candle.signal.shortEntry'),
        colTooltip: colEnterTag,
      },
      {
        colData: colShortExitData,
        name: nameExit,
        symbol: 'diamond',
        symbolSize: 11,
        color: tc.exit,
        tooltipPrefix: tr('candle.signal.shortExit'),
        colTooltip: colExitTag,
      },
    ];

    for (const signal of signalConfigs) {
      if (signal.colData >= 0) {
        options.series.push({
          name: signal.name,
          type: 'scatter',
          symbol: signal.symbol,
          symbolSize: signal.symbolSize,
          symbolRotate: signal.symbolRotate ?? 0,
          xAxisIndex: 0,
          yAxisIndex: 0,
          itemStyle: {
            color: signal.color,
            borderColor: t.surface,
            borderWidth: 1.5,
            opacity: 1,
          },
          tooltip: {
            valueFormatter: (value) => {
              if (Array.isArray(value)) {
                if (value.length > 0 && value[0]) {
                  // If tag column number get's too high, we get the full list as second argument (for no good reason)
                  const tag = Array.isArray(value[1])
                    ? value[1][signal.colTooltip]?.toString()
                    : value[1]?.toString();
                  const tagShort = tag.substring(0, 100);

                  // Show both prefix and tag
                  // Value would be in value[0] - but we don't show this to avoid showing the same data multiple times as it would correspond to the close price of the candle.
                  return `${signal.tooltipPrefix} ${tagShort ? `(${tagShort})` : ''}`;
                }
                // fall back to empty output if tag ain't set.
                return '';
              }
              // Fallback for single value
              return value ? `${signal.tooltipPrefix} ${value}` : '';
            },
          },
          encode: {
            x: colDate,
            y: signal.colData,
            tooltip:
              signal.colTooltip >= 0 ? [signal.colData, signal.colTooltip] : [signal.colData],
          },
        });
      }
    }
  }

  if ('main_plot' in props.plotConfig) {
    Object.entries(props.plotConfig.main_plot).forEach(([key, value]) => {
      const col = columns.findIndex((el) => el === key);
      if (col > 0) {
        addLegend(key);
        if (Array.isArray(options.series)) {
          options.series.push(generateCandleSeries(colDate, col, key, value));

          if (value.fill_to) {
            // Assign
            const fillColKey = `${key}-${value.fill_to}`;
            const fillCol = columns.findIndex((el) => el === fillColKey);
            const fillValue: IndicatorConfig = {
              color: value.color,
              type: ChartType.line,
            };
            const areaSeries = generateAreaCandleSeries(colDate, fillCol, key, fillValue, 0);

            const currentSeries = options.series[options.series.length - 1];
            if (currentSeries) {
              currentSeries['stack'] = key;
            }
            options.series.push(areaSeries);
          }
          options.series.splice(options.series.length - 1, 0);
        }
      } else {
        console.log(`element ${key} for main plot not found in columns.`);
      }
    });
  }

  // START Subplots
  if ('subplots' in props.plotConfig) {
    let plotIndex = 2;
    Object.entries(props.plotConfig.subplots).forEach(([key, value]) => {
      // define yaxis

      // Subplots are added from bottom to top - only the "bottom-most" plot stays at the bottom.
      // const currGridIdx = totalSubplots - plotIndex > 1 ? totalSubplots - plotIndex : plotIndex;
      const currGridIdx = plotIndex;
      if (Array.isArray(options.yAxis) && options.yAxis.length <= plotIndex) {
        options.yAxis.push({
          scale: true,
          gridIndex: currGridIdx,
          name: key,
          position: props.labelSide,
          nameLocation: 'middle',
          nameGap: NAMEGAP,
          axisLabel: {
            show: true,
            hideOverlap: true,
            overflow: 'truncate',
          },
          axisLine: { show: showAxisLine },
          axisTick: { show: false },
          splitLine: { show: false },
        });
      }
      if (Array.isArray(options.xAxis) && options.xAxis.length <= plotIndex) {
        options.xAxis.push({
          type: 'time',
          gridIndex: currGridIdx,
          axisLine: { onZero: false },
          axisTick: { show: false },
          axisLabel: { show: false },
          axisPointer: {
            label: { show: false },
          },
          splitLine: { show: false },
          splitNumber: 20,
        });
      }
      if (Array.isArray(chartOptions.value.dataZoom)) {
        // Must be set on the chartOptions object - options doesn't have dataZoom at this point
        chartOptions.value.dataZoom.forEach((el) =>
          el.xAxisIndex && Array.isArray(el.xAxisIndex) ? el.xAxisIndex.push(plotIndex) : null,
        );
      }
      if (options.grid && Array.isArray(options.grid)) {
        options.grid.push({
          left: MARGINLEFT,
          right: MARGINRIGHT,
          outerBoundsMode: 'none',
          bottom: `${(subplotCount - plotIndex + 1) * SUBPLOTHEIGHT}%`,
          height: `${SUBPLOTHEIGHT}%`,
        });
      }
      Object.entries(value).forEach(([sk, sv]) => {
        // entries per subplot
        const col = columns.findIndex((el) => el === sk);
        if (col > 0) {
          addLegend(sk);
          if (options.series && Array.isArray(options.series)) {
            options.series.push(generateCandleSeries(colDate, col, sk, sv, plotIndex));
            if (sv.fill_to) {
              // Assign
              const fillColKey = `${sk}-${sv.fill_to}`;
              const fillCol = columns.findIndex((el) => el === fillColKey);
              const fillValue: IndicatorConfig = {
                color: sv.color,
                type: ChartType.line,
              };
              const areaSeries = generateAreaCandleSeries(
                colDate,
                fillCol,
                sk,
                fillValue,
                plotIndex,
              );
              const currentSeries = options.series[options.series.length - 1];
              if (currentSeries) {
                currentSeries['stack'] = sk;
              }
              options.series.push(areaSeries);
            }
            options.series.splice(options.series.length - 1, 0);
          }
        } else {
          console.log(`element ${sk} was not found in the columns.`);
        }
      });

      plotIndex += 1;
    });
  }
  // END Subplots
  // Last subplot should show xAxis labels
  // if (options.xAxis && Array.isArray(options.xAxis)) {
  //   options.xAxis[options.xAxis.length - 1].axisLabel.show = true;
  //   options.xAxis[options.xAxis.length - 1].axisTick.show = true;
  // }
  if (Array.isArray(options.grid)) {
    // Last subplot is bottom
    const localGrid = options.grid[options.grid.length - 1];
    if (localGrid) {
      // Last subplot is bottom
      localGrid.bottom = 48;
      delete localGrid.top;
    }
  }

  const nameTrades = tr('candle.series.trades');
  // Insert trades into legend, after the default columns
  addLegend(nameTrades, 4);
  const tradesSeries: ScatterSeriesOption = generateTradeSeries(
    nameTrades,
    props.theme,
    props.dataset,
    filteredTrades.value,
  );
  if (Array.isArray(options.series)) {
    options.series.push(tradesSeries);
  }

  // Merge this into original data
  Object.assign(chartOptions.value, options);
  // console.log('chartOptions', chartOptions.value);
  candleChart.value?.setOption(chartOptions.value, {
    replaceMerge: ['series', 'grid', 'yAxis', 'xAxis', 'legend'],
    notMerge: initial,
  });
}

function initializeChartOptions() {
  // Ensure we start empty.
  candleChart.value?.setOption({}, { notMerge: true });

  chartOptions.value = {
    title: [
      {
        // text: this.chartTitle,
        show: false,
      },
    ],
    backgroundColor: 'rgba(0, 0, 0, 0)',
    useUTC: props.useUTC,
    animation: false,
    legend: {
      // Initial legend, further entries are pushed to the below list
      data: [
        tr('candle.series.candles'),
        tr('candle.series.volume'),
        tr('candle.series.entry'),
        tr('candle.series.exit'),
      ],
      left: MARGINLEFT,
      right: MARGINRIGHT,
      top: 4,
      type: 'scroll',
      icon: 'roundRect',
      itemWidth: 10,
      itemHeight: 10,
      itemGap: 16,
    },
    tooltip: {
      show: true,
      trigger: 'axis',
      renderMode: 'html',
      formatter: formatNovaCandleTooltip,
      axisPointer: {
        type: 'cross',
      },
      // positioning copied from https://echarts.apache.org/en/option.html#tooltip.position
      position(pos, params, dom, rect, size) {
        // tooltip will be fixed on the right if mouse hovering on the left,
        // and on the left if hovering on the right.
        const obj = { top: 72 };
        const mouseIsLeft = pos[0] < size.viewSize[0] / 2;
        obj[['left', 'right'][+mouseIsLeft]!] = (mouseIsLeft ? MARGINRIGHT : MARGINLEFT) + 8;
        return obj;
      },
    },
    axisPointer: {
      link: [{ xAxisIndex: 'all' }],
      label: {
        backgroundColor: tokens.value.tooltipBorder,
        color: tokens.value.text,
        borderRadius: 4,
        padding: [3, 6],
        fontSize: 11,
        formatter: (p: { axisDimension?: string; value: unknown }) =>
          p.axisDimension === 'y' && typeof p.value === 'number'
            ? priceText(p.value)
            : String(p.value ?? ''),
      },
    },

    dataZoom: [
      // Start values are recalculated once the data is known
      {
        type: 'inside',
        xAxisIndex: [0, 1],
        start: 80,
        end: 100,
      },
      {
        xAxisIndex: [0, 1],
        bottom: 8,
        left: MARGINLEFT,
        right: MARGINRIGHT,
        start: 80,
        end: 100,
        ...dataZoomPartial,
      },
    ],
    // visualMap: {
    //   //  TODO: this would allow to colorize volume bars (if we'd want this)
    //   //  Needs green / red indicator column in data.
    //   show: true,
    //   seriesIndex: 1,
    //   dimension: 5,
    //   pieces: [
    //     {
    //       max: 500000.0,
    //       color: downColor,
    //     },
    //     {
    //       min: 500000.0,
    //       color: upColor,
    //     },
    //   ],
    // },
  };

  console.log('Initialized');
  updateChart(true);
}

function updateSliderPosition() {
  if (!props.sliderPosition) return;

  const start = props.sliderPosition.startValue - props.dataset.timeframe_ms * 40;
  const end = props.sliderPosition.endValue
    ? props.sliderPosition.endValue + props.dataset.timeframe_ms * 40
    : props.sliderPosition.startValue + props.dataset.timeframe_ms * 80;
  if (candleChart.value) {
    candleChart.value.dispatchAction({
      type: 'dataZoom',
      dataZoomIndex: 0,
      startValue: start,
      endValue: end,
    });
  }
}

// const buyData = ref<number[][]>([]);
// const sellData = ref<number[][]>([]);
// createSignalData(colDate: number, colOpen: number, colBuy: number, colSell: number): void {
// Calculate Buy and sell Series
// if (!this.signalsCalculated) {
//   // Generate Buy and sell array (using open rate to display marker)
//   for (let i = 0, len = this.dataset.data.length; i < len; i += 1) {
//     if (this.dataset.data[i][colBuy] === 1) {
//       this.buyData.push([this.dataset.data[i][colDate], this.dataset.data[i][colOpen]]);
//     }
//     if (this.dataset.data[i][colSell] === 1) {
//       this.sellData.push([this.dataset.data[i][colDate], this.dataset.data[i][colOpen]]);
//     }
//   }
//   this.signalsCalculated = true;
// }
// }

onMounted(() => {
  initializeChartOptions();
});

watch(
  [
    () => props.useUTC,
    () => props.theme,
    () => props.plotConfig,
    () => props.colorUp,
    () => props.colorDown,
    // Series, legend and axis names are translated: rebuild the chart on a language switch.
    () => currentLocale(),
  ],
  () => initializeChartOptions(),
);

watch([() => props.dataset, () => props.heikinAshi, () => props.showMarkArea], () => updateChart());

watch(
  () => props.sliderPosition,
  () => updateSliderPosition(),
);
</script>

<template>
  <div class="h-full w-full">
    <ECharts v-if="hasData" ref="candleChart" :theme="echartsTheme" autoresize manual-update />
  </div>
</template>

<style scoped lang="css">
.echarts {
  width: 100%;
  min-height: 200px;
  /* TODO: height calculation is not working correctly - uses min-height for now */
  /* height: 600px; */
  height: 100%;
}
</style>
