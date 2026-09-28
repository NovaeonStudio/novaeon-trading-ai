# Contributing

Thanks for helping. Bug reports, fixes, translations, documentation and careful research are all welcome.

By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md). Security problems: please follow
[SECURITY.md](SECURITY.md) instead of opening an issue.

## Before you start

- **Small fixes:** open a pull request directly.
- **Bigger changes** (new pages, strategy changes, new exchanges): open an issue first so we can agree on the
  approach before you spend time on it.
- **Strategy changes need evidence.** A pull request that changes trading rules must include backtests on both
  Binance periods and on Hyperliquid, with return *and* maximum drawdown, run as described in
  [STRATEGY.md](STRATEGY.md#reproducing-the-backtests). "Looks better on one chart" is not enough.
- **Safety defaults stay safe.** Practice mode, 1× leverage, local-only access and opt-in telemetry are defaults
  on purpose. Changes that weaken them will not be merged.

## Setup

App (Node.js 22 or newer, pnpm via `corepack enable`):

```bash
pnpm install --frozen-lockfile
pnpm run dev
```

The dev server needs a running engine to log in to. Most UI work can also be done against the mocked data used by
the tests.

Bot and Sentinel: Python 3.12, Freqtrade 2026.8, and for Sentinel [Kev](https://github.com/jaredpalmer/kev) and MLX
on Apple Silicon. See [ARCHITECTURE.md](ARCHITECTURE.md).

## Checks

Run these before you open a pull request; CI runs the same:

```bash
pnpm run typecheck
pnpm run lint-ci
pnpm run test:unit
pnpm run build
```

Browser tests (optional locally, run in a separate workflow): `pnpm run test:e2e-chromium`. Chart snapshot
baselines are per platform; if you change charts, regenerate them with the "E2E" workflow's snapshot update job.

Python: keep scripts runnable with the standard library plus the packages the bot already uses. Run a backtest
before and after any strategy change and include both results.

## Style

- TypeScript and Vue: the repository's ESLint and Prettier settings (`pnpm run lint`).
- User-facing text: plain, short, honest. No hype, no "guaranteed", no profit promises. Numbers about performance
  always come with the maximum drawdown and the note that past results do not guarantee future results.
- Commits: one topic per commit, message in the imperative ("Fix stop line on 4h chart").

## Keeping up with upstream

The app is a fork of [FreqUI](https://github.com/freqtrade/frequi) (GPL-3.0). To take upstream fixes:

```bash
git remote add upstream https://github.com/freqtrade/frequi.git
git remote set-url --push upstream DISABLED   # never push to upstream
git fetch upstream --tags
git merge <release-tag>
```

Internal code names such as `ftbot` and the API types match the engine's REST API and are kept on purpose, so
merges stay small. After a merge, check that no upstream branding reappeared in the app (`grep -rn -iE
"freqtrade|frequi" src e2e`).

## License of contributions

By submitting a contribution you agree that it is licensed under the GNU General Public License, version 3, like
the rest of the repository (Sentinel weights and model-card changes: Apache-2.0).
