# Architecture

NovaeonTradingAI is four local programs that talk over HTTP on `127.0.0.1`, plus two outside services
(Hyperliquid and public news feeds). Nothing runs in a Novaeon cloud.

```mermaid
flowchart TB
    subgraph Mac["Your Mac"]
        direction TB
        UI["App<br/>Vue 3 + TypeScript<br/>(served by the engine's API server)"]
        subgraph Services["Background services (launchd)"]
            ENG["Trading engine :8081<br/>Freqtrade + BreakoutRegimeKev"]
            CTL["Control service :8082<br/>FastAPI"]
            SEN["Sentinel :8010<br/>MLX, Kev API"]
        end
        FILES[("user_data/<br/>configs, SQLite trades,<br/>decision log, settings")]
        KC[("macOS Keychain<br/>bot key")]
    end
    MM["MetaMask<br/>browser extension"]
    HL["Hyperliquid API"]
    NEWS["RSS: CoinDesk, Cointelegraph,<br/>Decrypt, The Block"]

    UI -->|"REST + JWT"| ENG
    UI -->|"REST, same token"| CTL
    UI <-->|"EIP-712 signature"| MM
    CTL -->|"token check"| ENG
    CTL -->|"force entry, stops"| ENG
    CTL --> FILES
    CTL --> KC
    CTL -->|"approve agent, balance"| HL
    ENG --> FILES
    ENG -->|"candles, order book, orders"| HL
    ENG -->|"headlines"| NEWS
    ENG -->|"/v1/systemone"| SEN
```

## Components

### App (`src/`)

Vue 3, TypeScript, Pinia, Nuxt UI, Tailwind CSS and ECharts, built with Vite into `dist/`. The engine's API server
serves the built files, so the app and the engine share one origin. Two modes:

- **Simple mode** (default): Home, My coins, History, Wallet, Strategy. Plain language, no trading jargon.
- **Pro mode**: Command Center, Cockpit, Positions (trade chart with entry, break-even, stop, liquidation and
  strategy levels; buy more; move stop), Markets, Trades, Strategy Lab, Journal and engine tools.

It is an installable web app (PWA) with browser notifications and a privacy mode that hides amounts.

### Trading engine (`bot/`)

[Freqtrade](https://github.com/freqtrade/freqtrade) 2026.8 runs the strategy `BreakoutRegimeKev`
([STRATEGY.md](STRATEGY.md)). Its REST API listens on `127.0.0.1:8081` and requires a login (JWT).

- `bot/bin/run-bot.sh` starts the engine in the mode stored in `user_data/mode.json`:
  - **practice**: `dry_run`, a practice balance from `user_data/practice.json`, and a SQLite database per practice
    run (starting over creates a fresh database; the old one is kept);
  - **live**: `user_data/live.json` (`dry_run: false`, the spending cap as `available_capital`, stop-losses on the
    exchange), a separate database, and the bot key read from the Keychain into the engine's environment. Without a
    key it refuses to start instead of silently falling back to practice.
- `installer/lib/ensure-engine-patches.sh` (installed as `bin/ensure-engine-patches.sh`) re-applies one small engine patch after updates: a larger SQLite connection
  pool, because the default pool could be exhausted under concurrent app requests and stall the trading loop.
- `bot/bin/watchdog.py` is a read-only monitor that reports only changes: bot not responding, stopped, emergency
  brake on, drawdown of 15% or more, serious errors, engine patch missing.

### Control service (`bot/bin/control.py`)

A small FastAPI service on `127.0.0.1:8082` for everything the engine does not do itself. It accepts the same
bearer token the app uses for the engine and verifies it against the engine, so there is no second login. Every
state change is appended to an audit log.

| Area | Endpoints |
|---|---|
| Status | `GET /control/status`, `GET /control/balance/{address}` |
| Wallet | `POST /control/agent/start`, `POST /control/agent/confirm`, `POST /control/wallet/forget` |
| Practice money | `GET /control/practice`, `POST /control/practice/add`, `POST /control/practice/reset` |
| Mode switch | `POST /control/mode` (practice ↔ live, with all live-mode checks) |
| Manual trading | `POST /control/buy`, `GET /control/stops`, `POST /control/trades/{id}/stop` |
| Chart levels | `GET /control/levels`, `GET /control/trades/{id}/levels` |
| Settings | AI leverage on/off and whether this Mac allows it |

### Sentinel (`novaeon-kev/`)

The MLX build of [Novaeon Sentinel 9B](SENTINEL.md) (8-bit on Macs with 16 GB or more, 4-bit on 8 GB Macs), served
with Kev's server on `127.0.0.1:8010` (`/v1/systemone`). The strategy calls it once per new position, at most every
2 minutes per coin. If it does not answer, the bot trades at 1× without the news check.

## Key flows

### A new position

```mermaid
sequenceDiagram
    participant E as Engine (strategy)
    participant N as News feeds
    participant S as Sentinel
    participant H as Hyperliquid
    E->>E: hourly candle closes: breakout + 2x volume + BTC above EMA50?
    E->>N: headlines (cached 15 min)
    alt no headlines about the coin in the last 48 h
        E->>E: allow at 1x
    else headlines found
        E->>S: major_negative + outlook
        alt P(major negative) >= 0.30
            E->>E: block, write decision log
        else allowed
            E->>E: leverage 1x (2x/3x only if AI leverage is on)
            E->>H: limit order (practice mode: simulated)
        end
    end
```

### Going live

```mermaid
sequenceDiagram
    actor U as You
    participant A as App
    participant C as Control service
    participant K as Keychain
    participant M as MetaMask
    participant H as Hyperliquid
    U->>A: Connect MetaMask
    A->>C: agent/start (your wallet address)
    C->>C: generate bot key
    C->>K: store bot key (pending)
    C-->>A: bot address + message to sign
    A->>M: sign ApproveAgent (EIP-712)
    M-->>A: signature (your key stays in MetaMask)
    A->>C: agent/confirm (signature)
    C->>H: approveAgent
    C->>H: check that the agent is listed
    C->>K: store bot key (active)
    U->>A: spending cap + type REAL MONEY
    A->>C: mode = live
    C->>C: checks: agent approved, balance >= cap >= 20 USDC
    C->>C: write live config, restart engine
```

## Where data lives

All under the install directory (`~/NovaeonTradingAI`), mostly in `user_data/`:

| What | Where |
|---|---|
| Engine and app settings, app login | engine config files (`config.json`, `bot.json`) |
| Trades | SQLite databases (one per practice run, one for live) |
| Mode, wallet address, practice ledger, manual stops, settings | small JSON files written with mode 600 |
| AI decisions | `kev_decisions.jsonl` and the trade's custom data |
| Audit log of control actions | `control-audit.jsonl` |
| Bot key (live trading) | macOS login Keychain, never in a file |
| Your wallet key | only in MetaMask |

## Ports

| Port | Service | Bound to |
|---|---|---|
| 8081 | Trading engine API + app | 127.0.0.1 |
| 8082 | Control service | 127.0.0.1 |
| 8010 | Sentinel | 127.0.0.1 |

To use the app from your phone, put your own authenticated tunnel or VPN in front of it. Do not expose these ports
to the internet.
