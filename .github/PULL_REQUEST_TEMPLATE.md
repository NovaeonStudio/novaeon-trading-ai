## What and why

<!-- One or two sentences. Link the issue: Fixes #123 -->

## Changes

-

## How I tested it

<!-- Commands you ran, screenshots for UI changes (practice mode, privacy mode on). -->

## Checklist

- [ ] `pnpm run typecheck`, `pnpm run lint-ci`, `pnpm run test:unit` and `pnpm run build` pass
- [ ] UI text is plain and honest; performance numbers come with max drawdown and "past results don't guarantee future results"
- [ ] Safety defaults unchanged (practice mode, 1x leverage, local-only, opt-in telemetry), or the change is explained above
- [ ] **Strategy changes only:** backtests before/after on both Binance periods and Hyperliquid, with return and max drawdown
- [ ] No keys, passwords, wallet addresses or personal paths in the diff
