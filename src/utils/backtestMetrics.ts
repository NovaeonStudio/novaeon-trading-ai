import type { StrategyBacktestResult, Trade } from '@/types';
import { t } from '@/i18n';

function getSortedTrades(trades: Trade[]): Trade[] {
  const sortedTrades = trades.slice().sort((a, b) => (a.profit_ratio ?? 0) - (b.profit_ratio ?? 0));
  return sortedTrades;
}

function getBestPair(trades: Trade[]) {
  const value = trades[trades.length - 1];
  if (!value) {
    return 'N/A';
  }
  return `${value.pair} ${formatPercent(value.profit_ratio, 2)}`;
}

function getWorstPair(trades: Trade[]) {
  const value = trades[0];
  if (!value) {
    return 'N/A';
  }
  return `${value.pair} ${formatPercent(value.profit_ratio, 2)}`;
}

function useFormatPriceStake(stake_currency_decimals: number, stake_currency: string) {
  const formatPriceStake = (price) => {
    return `${formatPrice(price, stake_currency_decimals)} ${stake_currency}`;
  };
  return formatPriceStake;
}

export function generateBacktestMetricRows(result: StrategyBacktestResult) {
  const sortedTrades = getSortedTrades(result.trades);
  const bestPair = getBestPair(sortedTrades);
  const worstPair = getWorstPair(sortedTrades);
  const pairSummary = result.results_per_pair[result.results_per_pair.length - 1];

  const formatPriceStake = useFormatPriceStake(
    result.stake_currency_decimals,
    result.stake_currency,
  );

  // Transpose Result into readable format
  const shortMetrics =
    result.trade_count_short && result.trade_count_short > 0
      ? [
          { '___ ': '___' },
          {
            [t('backtest.metric.longShort')]:
              `${result.trade_count_long} / ${result.trade_count_short}`,
          },
          {
            [t('backtest.metric.totalProfitLong')]: `${formatPercent(
              result.profit_total_long || 0,
            )} | ${formatPriceStake(result.profit_total_long_abs)}`,
          },
          {
            [t('backtest.metric.totalProfitShort')]: `${formatPercent(
              result.profit_total_short || 0,
            )} | ${formatPriceStake(result.profit_total_short_abs)}`,
          },
        ]
      : [];

  /** Label of a metric computed on the wallet balance, e.g. "Max drawdown (wallet balance)". */
  const wb = (metric: string) => t('backtest.metric.walletSuffix', { metric });
  const walletBalanceMetrics = result.wallet_stats
    ? [
        { [t('backtest.metric.walletSection')]: '' },
        {
          [wb(t('backtest.metric.maxDrawdown'))]: formatPercent(
            result.wallet_stats.max_drawdown_account,
          ),
        },
        {
          [wb(t('backtest.metric.maxDrawdownAbs'))]: formatPriceStake(
            result.wallet_stats.max_drawdown_abs,
          ),
        },
        {
          [wb(t('backtest.metric.drawdownDuration'))]:
            result.wallet_stats.drawdown_duration ?? 'N/A',
        },
        {
          [wb(t('backtest.metric.profitAtDrawdown'))]:
            `${formatPriceStake(result.wallet_stats.max_drawdown_high)} | ${formatPriceStake(
              result.wallet_stats.max_drawdown_low,
            )}`,
        },
        // { 'Max Drawdown dates (wallet balance)': formatPercent(result.wallet_stats.max_drawdown_account) },
        {
          [wb(t('backtest.metric.drawdownStart'))]: timestampms(
            result.wallet_stats?.drawdown_start_ts ?? 0,
          ),
        },
        {
          [wb(t('backtest.metric.drawdownEnd'))]: timestampms(
            result.wallet_stats?.drawdown_end_ts ?? 0,
          ),
        },
        {
          [wb('Sortino')]: formatNumber(result.wallet_stats.sortino, 2),
        },
        {
          [wb('Sharpe')]: formatNumber(result.wallet_stats.sharpe, 2),
        },
        {
          [wb('Calmar')]: formatNumber(result.wallet_stats.calmar, 2),
        },
      ]
    : [];

  const tmp = [
    {
      [t('backtest.metric.totalProfit')]:
        `${formatPercent(result.profit_total)} | ${formatPriceStake(result.profit_total_abs)}`,
    },
    {
      CAGR: `${result.cagr ? formatPercent(result.cagr) : 'N/A'}`,
    },
    {
      Sortino: formatNumber(result.sortino, 2),
    },
    {
      Sharpe: formatNumber(result.sharpe, 2),
    },
    {
      Calmar: formatNumber(result.calmar, 2),
    },
    {
      [t('backtest.metric.sqn')]: formatNumber(result.sqn, 2),
    },
    {
      [t('backtest.metric.pValue')]: formatNumber(result.p_value, 3),
    },
    {
      [result.expectancy_ratio
        ? t('backtest.metric.expectancyRatio')
        : t('backtest.metric.expectancy')]: `${
        result.expectancy
          ? result.expectancy_ratio
            ? `${formatNumber(result.expectancy, 2)} (${formatNumber(result.expectancy_ratio, 2)})`
            : formatNumber(result.expectancy, 2)
          : 'N/A'
      }`,
    },
    {
      [t('backtest.metric.profitFactor')]: formatNumber(result.profit_factor, 3),
    },
    {
      [t('backtest.metric.totalTrades')]:
        `${result.total_trades} / ${formatNumber(result.trades_per_day, 2)}`,
    },
    // { 'First trade': result.backtest_fi },
    // { 'First trade Pair': result.backtest_best_day },
    {
      [t('backtest.metric.bestDay')]:
        `${formatPercent(result.backtest_best_day, 2)} | ${formatPriceStake(
          result.backtest_best_day_abs,
        )}`,
    },
    {
      [t('backtest.metric.worstDay')]:
        `${formatPercent(result.backtest_worst_day, 2)} | ${formatPriceStake(
          result.backtest_worst_day_abs,
        )}`,
    },

    {
      [t('backtest.metric.winDrawLoss')]:
        `${pairSummary?.wins} / ${pairSummary?.draws} / ${pairSummary?.losses} ${
          isNotUndefined(pairSummary?.winrate)
            ? '(WR: ' +
              formatPercent(
                result.results_per_pair[result.results_per_pair.length - 1]?.winrate ?? 0,
                2,
              ) +
              ')'
            : ''
        }`,
    },
    {
      [t('backtest.metric.daysWinDrawLoss')]:
        `${result.winning_days} / ${result.draw_days} / ${result.losing_days}`,
    },
    {
      // TODO: min/max/avg trade duration should be aligned with the terminal output
      [t('backtest.metric.minDurationWinners')]: humanizeDurationFromSeconds(
        result.winner_holding_min_s,
      ),
    },
    {
      [t('backtest.metric.avgDurationWinners')]: humanizeDurationFromSeconds(
        result.winner_holding_avg_s,
      ),
    },
    {
      [t('backtest.metric.maxDurationWinners')]: humanizeDurationFromSeconds(
        result.winner_holding_max_s,
      ),
    },
    {
      [t('backtest.metric.minDurationLosers')]: humanizeDurationFromSeconds(
        result.loser_holding_min_s,
      ),
    },
    {
      [t('backtest.metric.avgDurationLosers')]: humanizeDurationFromSeconds(
        result.loser_holding_avg_s,
      ),
    },
    {
      [t('backtest.metric.maxDurationLosers')]: humanizeDurationFromSeconds(
        result.loser_holding_max_s,
      ),
    },
    {
      [t('backtest.metric.maxConsecutive')]:
        result.max_consecutive_wins === undefined
          ? 'N/A'
          : `${result.max_consecutive_wins} / ${result.max_consecutive_losses}`,
    },
    { [t('backtest.metric.rejectedSignals')]: result.rejected_signals },
    {
      [t('backtest.metric.timeouts')]:
        `${result.timedout_entry_orders} / ${result.timedout_exit_orders}`,
    },
    {
      [t('backtest.metric.canceledTradeEntries')]: result.canceled_trade_entries ?? 'N/A',
    },
    {
      [t('backtest.metric.canceledEntryOrders')]: result.canceled_entry_orders ?? 'N/A',
    },
    {
      [t('backtest.metric.replacedEntryOrders')]: result.replaced_entry_orders ?? 'N/A',
    },

    ...shortMetrics,

    { ___: '___' },
    {
      [t('backtest.metric.minMaxBalanceClosed')]:
        `${formatPriceStake(result.csum_min)} / ${formatPriceStake(result.csum_max)}`,
    },
    {
      [t('backtest.metric.minMaxBalanceWallet')]:
        `${formatPriceStake(result.wallet_stats?.low_balance)} / ${formatPriceStake(result.wallet_stats?.high_balance)}`,
    },
    { [t('backtest.metric.marketChange')]: formatPercent(result.market_change) },
    { '___  ': '___' },
    {
      [t('backtest.metric.maxDrawdownAccount')]: formatPercent(result.max_drawdown_account),
    },
    {
      [t('backtest.metric.maxDrawdownAbs')]: formatPriceStake(result.max_drawdown_abs),
    },
    {
      [t('backtest.metric.drawdownDuration')]: result.drawdown_duration ?? 'N/A',
    },
    {
      [t('backtest.metric.profitAtDrawdown')]:
        `${formatPriceStake(result.max_drawdown_high)} | ${formatPriceStake(
          result.max_drawdown_low,
        )}`,
    },
    { [t('backtest.metric.drawdownStart')]: timestampms(result.drawdown_start_ts) },
    { [t('backtest.metric.drawdownEnd')]: timestampms(result.drawdown_end_ts) },
    ...walletBalanceMetrics,
    { '___    ': '___' },
    {
      [t('backtest.metric.bestPair')]:
        `${result.best_pair.key} ${formatPercent(result.best_pair.profit_total)}`,
    },
    {
      [t('backtest.metric.worstPair')]:
        `${result.worst_pair.key} ${formatPercent(result.worst_pair.profit_total)}`,
    },
    { [t('backtest.metric.bestTrade')]: bestPair },
    { [t('backtest.metric.worstTrade')]: worstPair },
  ];
  return tmp;
}

function capitalizeFirstLetter(str: string): string {
  return str.charAt(0).toUpperCase() + str.slice(1);
}

function formatTradingMode(result: StrategyBacktestResult) {
  if (!result.trading_mode || !result.margin_mode) {
    return {};
  }
  const value =
    result.trading_mode === 'spot'
      ? capitalizeFirstLetter(result.trading_mode)
      : `${capitalizeFirstLetter(result.margin_mode)} ${capitalizeFirstLetter(result.trading_mode)}`;
  return { [t('backtest.metric.tradingMode')]: value };
}

export function generateBacktestSettingRows(result: StrategyBacktestResult) {
  const formatPriceStake = useFormatPriceStake(
    result.stake_currency_decimals,
    result.stake_currency,
  );
  const tradingMode = formatTradingMode(result);

  return [
    { [t('backtest.metric.backtestingFrom')]: timestampms(result.backtest_start_ts) },
    { [t('backtest.metric.backtestingTo')]: timestampms(result.backtest_end_ts) },
    ...(Object.keys(tradingMode).length !== 0 ? [tradingMode] : []),
    {
      [t('backtest.metric.runTime')]: humanizeDurationFromSeconds(
        result.backtest_run_end_ts - result.backtest_run_start_ts,
      ),
    },
    { [t('backtest.metric.maxOpenTrades')]: result.max_open_trades },
    { [t('backtest.metric.timeframe')]: result.timeframe },
    { [t('backtest.metric.timeframeDetail')]: result.timeframe_detail || 'N/A' },
    { [t('backtest.metric.timerange')]: result.timerange },
    { [t('backtest.metric.stoploss')]: formatPercent(result.stoploss, 2) },
    { [t('backtest.metric.trailingStop')]: result.trailing_stop },
    {
      [t('backtest.metric.trailOnlyOffset')]: result.trailing_only_offset_is_reached,
    },
    { [t('backtest.metric.trailingStopPositive')]: formatNumber(result.trailing_stop_positive) },
    {
      [t('backtest.metric.trailingStopPositiveOffset')]: formatNumber(
        result.trailing_stop_positive_offset,
      ),
    },
    { [t('backtest.metric.customStoploss')]: result.use_custom_stoploss },
    { ROI: JSON.stringify(result.minimal_roi) },
    {
      [t('backtest.metric.useExitSignal')]: result.use_exit_signal ?? result.use_sell_signal,
    },
    {
      [t('backtest.metric.exitProfitOnly')]: result.exit_profit_only ?? result.sell_profit_only,
    },
    {
      [t('backtest.metric.exitProfitOffset')]: formatNumber(
        result.exit_profit_offset ?? result.sell_profit_offset,
      ),
    },
    { [t('backtest.metric.enableProtections')]: result.enable_protections },
    {
      [t('backtest.metric.startingBalance')]: formatPriceStake(result.starting_balance),
    },
    {
      [t('backtest.metric.finalBalance')]: formatPriceStake(result.final_balance),
    },
    {
      [t('backtest.metric.avgStake')]: formatPriceStake(result.avg_stake_amount),
    },
    {
      [t('backtest.metric.totalVolume')]: formatPriceStake(result.total_volume),
    },
  ];
}

/** Selectable options for backtest charts.
 * selection happens through the settings page
 */
export const availableBacktestMetrics = computed(() => [
  { field: 'sqn', header: 'SQN' },
  { field: 'cagr', header: 'CAGR' },
  { field: 'calmar', header: 'Calmar' },
  { field: 'p_value', header: t('backtest.metric.pValue') },
  { field: 'expectancy', header: t('backtest.metric.expectancy') },
  { field: 'profit_factor', header: t('backtest.metric.profitFactor') },
  { field: 'sharpe', header: 'Sharpe' },
  { field: 'sortino', header: 'Sortino' },
  { field: 'max_drawdown_account', header: t('backtest.metric.maxDrawdown'), is_ratio: true },
]);
