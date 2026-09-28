import type { Order, PairHistory, Trade, BTOrder } from '@/types';
import { t } from '@/i18n';

import type {
  MarkAreaComponentOption,
  MarkLineComponentOption,
  MarkPointComponentOption,
  ScatterSeriesOption,
  TooltipComponentOption,
} from 'echarts';

function buildTooltipCost(order: Order | BTOrder, quoteCurrency: string): string {
  return `${order.ft_order_side === 'buy' ? '+' : '-'}${formatPriceCurrency(
    'cost' in order ? order.cost : order.amount * order.safe_price,
    quoteCurrency,
  )}`;
}

function sideTitle(trade: Trade, side: 'entry' | 'exit' | 'adjustment'): string {
  if (side === 'entry')
    return trade.is_short ? t('chart.market.shortEntry') : t('chart.market.longEntry');
  if (side === 'exit')
    return trade.is_short ? t('chart.market.shortExit') : t('chart.market.longExit');
  return trade.is_short ? t('chart.market.shortAdjustment') : t('chart.market.longAdjustment');
}

function buildToolTip(
  trade: Trade,
  order: Order | BTOrder,
  side: 'entry' | 'exit',
  quoteCurrency: string,
): string {
  let tooltip = `${sideTitle(trade, side)}
  ${formatPercent(trade.profit_ratio)} ${
    trade.profit_abs ? '(' + formatPriceCurrency(trade.profit_abs, quoteCurrency) + ')' : ''
  }
  ${buildTooltipCost(order, quoteCurrency)}
  ${t('chart.market.enterTag', { tag: trade.enter_tag ?? '' })}
  ${t('chart.market.orderPrice', { price: formatPriceCurrency(order.safe_price, quoteCurrency) })}`;
  tooltip += `${'ft_order_tag' in order && order.ft_order_tag && trade.enter_tag != order.ft_order_tag ? '\n' + t('chart.market.orderTag', { tag: order.ft_order_tag }) : ''}`;
  tooltip += `${trade.exit_reason ? '\n' + t('chart.market.exitTag', { tag: trade.exit_reason }) : ''}`;
  return tooltip;
}

function buildAdjustmentToolTip(
  trade: Trade,
  order: Order | BTOrder,
  quoteCurrency: string,
): string {
  let tooltip = `${sideTitle(trade, 'adjustment')}
  ${buildTooltipCost(order, quoteCurrency)}
  ${t('chart.market.enterTag', { tag: trade.enter_tag ?? '' })}`;
  tooltip += `${'ft_order_tag' in order && order.ft_order_tag ? '\n' + t('chart.market.orderTag', { tag: order.ft_order_tag }) : ''}`;

  return tooltip;
}

const ADJUSTMENT_SYMBOL =
  'path://m 52.444161,104.1909 8.386653,25.34314 8.386651,25.34313 -16.731501,0.0422 -16.731501,0.0422 8.344848,-25.38539 z m 0.08656,-48.368126 8.386652,25.343139 8.386652,25.343137 -16.731501,0.0422 -16.731502,0.0422 8.344848,-25.385389 z';
const OPEN_CLOSE_SYMBOL =
  'path://m 102.20764,19.885384 h 24.1454 v 41.928829 h -24.1454 z m 12.17344,36.423813 8.38665,25.343139 8.38666,25.343134 -16.7315,0.0422 -16.731507,0.0422 8.344847,-25.385386 z';

/** Return trade entries for charting (entry = profit-ish, exit = accent, adjustments = secondary). */
function getTradeEntries(
  dataset: PairHistory,
  trades: Trade[],
  colors: ReturnType<typeof novaTradeColors>,
) {
  const tradeData: (number | string)[][] = [];
  // Return schema:
  // 0: Timeframe
  // 1: rate
  // 2: symbol
  // 3: symbol rotate
  // 4: color
  // 5: label
  // 6: tooltip
  const stop_ts_adjusted = dataset.data_stop_ts + dataset.timeframe_ms;
  for (const trade of trades) {
    // const trade: Trade = trades[i];
    const openTs = trade.open_fill_timestamp ?? trade.open_timestamp;
    if (
      // Trade is open or closed and within timerange
      roundTimeframe(dataset.timeframe_ms ?? 0, trade.open_timestamp) <= stop_ts_adjusted ||
      !trade.close_timestamp ||
      (trade.close_timestamp && trade.close_timestamp >= dataset.data_start_ts)
    ) {
      if (trade.orders) {
        for (const [j, order] of trade.orders.entries()) {
          const orderTs =
            order.order_filled_timestamp ??
            ('order_timestamp' in order ? order.order_timestamp : trade.open_timestamp);
          const { quoteCurrency } = splitTradePair(trade.quote_currency ?? trade.pair ?? '');
          if (
            orderTs &&
            roundTimeframe(dataset.timeframe_ms ?? 0, orderTs) <= stop_ts_adjusted &&
            orderTs > dataset.data_start_ts
          ) {
            // Trade entry
            if (j === 0) {
              tradeData.push([
                roundTimeframe(dataset.timeframe_ms ?? 0, openTs),
                order.safe_price,
                OPEN_CLOSE_SYMBOL,
                order.ft_order_side == 'sell' ? 180 : 0,
                colors.entry,
                order.order_filled_timestamp
                  ? trade.is_short
                    ? t('chart.market.short')
                    : t('chart.market.long')
                  : trade.is_short
                    ? t('chart.market.shortOpen')
                    : t('chart.market.longOpen'),
                buildToolTip(trade, order, 'entry', quoteCurrency),
              ]);
              // Trade exit
            } else if (j === trade.orders.length - 1 && trade.close_timestamp) {
              if (
                roundTimeframe(dataset.timeframe_ms ?? 0, trade.close_timestamp) <=
                  stop_ts_adjusted &&
                trade.close_timestamp > dataset.data_start_ts &&
                trade.is_open === false
              ) {
                tradeData.push([
                  roundTimeframe(dataset.timeframe_ms ?? 0, trade.close_timestamp),
                  order.safe_price,
                  OPEN_CLOSE_SYMBOL,
                  trade.is_short ? 0 : 180,
                  colors.exit,
                  formatPercent(trade.profit_ratio, 2),
                  buildToolTip(trade, order, 'exit', quoteCurrency),
                ]);
              }
            }
            // Position adjustment
            else {
              if (
                order.ft_order_side !== 'stoploss' ||
                ('filled' in order && (order.filled ?? 0) > 0)
              ) {
                // Don't show stoploss orders that haven't been filled
                tradeData.push([
                  roundTimeframe(dataset.timeframe_ms ?? 0, orderTs),
                  order.safe_price,
                  ADJUSTMENT_SYMBOL,
                  order.ft_order_side == 'sell' ? 180 : 0,
                  colors.adjustment,
                  '',
                  buildAdjustmentToolTip(trade, order, quoteCurrency),
                ]);
              }
            }
          }
        }
      }
    }
  }
  return { tradeData };
}

/** Stop line name (module-level helper: `t` is the chart tokens inside generateTradeSeries). */
function stoplossName(): string {
  return t('chart.market.stoploss');
}

/**
 *  Generate Series displaying trades
 *  This may include trades, orders, and eventually other things related to the trade.
 */
export function generateTradeSeries(
  nameTrades: string,
  theme: string,
  dataset: PairHistory,
  trades: Trade[],
): ScatterSeriesOption {
  const t = NOVA_CHART_TOKENS[theme === 'light' ? 'light' : 'dark'];
  const colors = novaTradeColors(t);
  const { tradeData } = getTradeEntries(dataset, trades, colors);

  const openTrade = trades.find((t) => t.is_open);

  const tradesSeries: ScatterSeriesOption = {
    name: nameTrades,
    type: 'scatter',
    // Legend key only; each marker is colored per data item (entry / exit / adjustment).
    color: t.textMuted,
    xAxisIndex: 0,
    yAxisIndex: 0,
    encode: {
      x: 0,
      y: 1,
      label: 5,
      tooltip: 6,
    },
    label: {
      show: true,
      fontSize: 11,
      fontWeight: 600,
      fontFamily: t.fontFamily,
      backgroundColor: t.tooltipBg,
      borderColor: t.tooltipBorder,
      borderWidth: 1,
      borderRadius: 4,
      padding: [2, 5],
      color: t.text,
      rotate: 75,
      offset: [10, 0],
      align: 'left',
    },
    itemStyle: {
      color: (v) => (v.data ? v.data[4] : t.neutral),
      borderColor: t.surface,
      borderWidth: 1,
      opacity: 1,
    },
    symbol: (v) => v[2],
    symbolRotate: (v) => v[3],
    symbolSize: 14,
    data: tradeData,
  };
  // Show distance to stoploss
  if (openTrade) {
    // Ensure to import and "use" whatever feature in candleChart! (MarkLine, MarkArea, ...)
    // Offset to avoid having the line at the very end of the chart
    const offset = dataset.timeframe_ms * 10;

    tradesSeries.markLine = {
      symbol: 'none',
      label: {
        show: true,
        position: 'middle',
        color: t.textMuted,
        fontSize: 11,
        fontFamily: t.fontFamily,
      },
      data: [
        [
          {
            name: stoplossName(),
            yAxis: openTrade.stop_loss_abs,
            lineStyle: {
              color: colors.stop,
              type: 'dashed',
              width: 1,
            },
            xAxis:
              dataset.data_stop_ts - offset > openTrade.open_timestamp
                ? openTrade.open_timestamp
                : dataset.data_stop_ts - offset,
          },
          {
            lineStyle: {
              color: colors.stop,
              type: 'dashed',
              width: 1,
            },
            yAxis: openTrade.stop_loss_abs,
            xAxis: openTrade.close_timestamp ?? dataset.data_stop_ts + dataset.timeframe_ms,
          },
        ],
      ],
    };
  }
  return tradesSeries;
}

export function generateMarkArea(
  dataset: PairHistory,
  enabled: boolean,
  markAreaZIndex?: number | undefined,
): {
  markArea?: MarkAreaComponentOption;
  markLine?: MarkLineComponentOption;
  markPoint?: MarkPointComponentOption;
  tooltip?: TooltipComponentOption;
} {
  if (!dataset.annotations || !enabled) return {};

  const markArea: MarkAreaComponentOption = {
    label: {
      position: 'insideTop',
    },
    z: markAreaZIndex ?? 1,
    data: dataset.annotations
      .filter((area) => area.type === 'area')
      .map((area) => {
        return [
          {
            z2: area.z_index ?? 1,
            xAxis: area.start,
            yAxis: area.y_start,
            itemStyle: {
              color: area.color,
            },
            label: {
              formatter: area.label,
            },
          },
          {
            z2: area.z_index ?? 1,
            xAxis: area.end,
            yAxis: area.y_end,
          },
        ];
      }),
  };
  const markLine: MarkLineComponentOption = {
    label: {
      position: 'middle',
    },
    symbol: ['none', 'none'],
    z: markAreaZIndex ?? 1,
    data: dataset.annotations
      .filter((line) => line.type === 'line')
      .map((line) => {
        return [
          {
            name: line.label,
            xAxis: line.start,
            yAxis: line.y_start,
            lineStyle: {
              color: line.color,
              width: line.width ?? 1,
              type: line.line_style ?? 'solid',
            },
            z2: line.z_index ?? 1,
          },
          {
            xAxis: line.end,
            yAxis: line.y_end,
            z2: line.z_index ?? 1,
          },
        ];
      }),
  };

  const markPoint: MarkPointComponentOption = {
    label: {
      position: 'top',
      show: true,
    },
    z: markAreaZIndex ? markAreaZIndex : 5,
    data: dataset.annotations
      .filter((point) => point.type === 'point')
      .map((point) => {
        return {
          name: point.label ?? '',
          xAxis: point.x,
          yAxis: point.y,
          itemStyle: {
            color: point.color,
          },
          label: {
            formatter: '{b}',
          },
          symbolSize: point.size ?? 10,
          symbol: point.shape ?? 'circle',
          symbolRotate: point.rotate,
          z2: point.z_index ?? 1,
        };
      }),
  };
  return {
    markArea,
    markLine,
    markPoint,
    tooltip: {
      show: false,
    },
  };
}

export function generateMarkAreaSeries(
  dataset: PairHistory,
  enabled: boolean,
  markAreaZIndex?: number | undefined,
): ScatterSeriesOption | undefined {
  if (!dataset.annotations || !enabled) {
    return undefined;
  }
  // Invisible series added to chart to work around marklines bug
  // TODO: https://github.com/apache/echarts/issues/21300
  return {
    // Invisible
    type: 'scatter',
    symbol: 'none',
    xAxisIndex: 0,
    ...generateMarkArea(dataset, enabled, markAreaZIndex),
  };
}
