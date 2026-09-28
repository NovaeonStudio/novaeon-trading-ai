# Security

NovaeonTradingAI can trade real money, so we take security reports seriously and answer them first.

## Reporting a vulnerability

**Please do not open a public issue for security problems.**

- Preferred: GitHub's private vulnerability reporting:
  [open a private security advisory](https://github.com/NovaeonStudio/novaeon-trading-ai/security/advisories/new)
  (the **Security** tab of the repository).
- Or email **office@novaeon.studio** with "Security" in the subject.

Please include what you found, how to reproduce it, and what an attacker could do with it. We will confirm receipt
within 3 working days, keep you updated, and credit you in the release notes unless you prefer not to be named.
Please give us a reasonable time to ship a fix before you publish details.

Supported versions: the latest release. Fixes are not backported.

In scope: this repository (app, bot, control service, installer, model serving code) and the published Sentinel
weights. Out of scope: Hyperliquid, MetaMask, Freqtrade and Kev themselves (report to those projects), and attacks
that need someone who is already logged in to your Mac as you.

## What the bot key can and cannot do

Live trading uses two keys:

| Key | Where it lives | What it can do |
|---|---|---|
| **Your wallet key** | Only in MetaMask | Everything: deposits, withdrawals, transfers. NovaeonTradingAI never sees it. |
| **Bot key** (Hyperliquid "API wallet") | macOS login Keychain, service `novaeon-trading-agent` | Place and cancel orders for your Hyperliquid account. **It cannot withdraw or transfer funds.** |

How the bot key is created: the control service generates a fresh random key on your Mac and stores it in the
Keychain. MetaMask then asks you to sign one Hyperliquid `ApproveAgent` message (named "NovaeonTradingAI"), which
allows that key to trade for your account. The app checks with Hyperliquid that the approval is registered.

What this means in practice:

- Someone who steals the bot key **cannot take your money out**. They could still place bad trades that lose money.
  If you suspect a leak, remove the API wallet on Hyperliquid's API page (or approve a new one), and disconnect the
  wallet in the app.
- Live mode can only use the amount you set as the spending cap.
- Switching to live requires a funded account, an approved bot key, the cap, and typing `REAL MONEY`.

## Where secrets live

| Secret | Where |
|---|---|
| Bot key | macOS login Keychain (`novaeon-trading-agent`; a not-yet-approved key under `novaeon-trading-agent-pending`). Never written to a file or a log. When the engine starts in live mode it reads the key from the Keychain into its process environment. |
| App login password, API token secrets | Generated at random during install; stored in the engine's config (`user_data/bot.json`) and, for you to look up, in `~/NovaeonTradingAI/login.txt` (file mode 600). `bin/novaeon password` sets a new one. |
| Wallet address, mode, practice ledger, manual stops | JSON files in `user_data/`, written with file mode 600 |
| Your wallet key and seed phrase | Only MetaMask. The app never asks for them. **Nobody from Novaeon will ever ask for them.** |

The configs in this repository ship with empty exchange keys, placeholder passwords and `dry_run: true`.

## Network exposure

- All services listen on `127.0.0.1` only: engine and app (8081), control service (8082), Sentinel (8010).
- The control service accepts only requests that carry a valid engine login token.
- Outbound connections: Hyperliquid (market data, orders, agent approval), four public news RSS feeds, Hugging Face
  (model download during install), and, only if you agreed during install, one anonymous install count.
- Do not expose the ports to the internet. If you want to reach the app from your phone, use your own
  authenticated VPN or tunnel.

## Known limitations

- Anyone who can run programs as your macOS user can read your Keychain items (after macOS asks, depending on
  settings), your config files and the environment of the engine process. Protect your Mac account with a strong
  password and FileVault.
- The app is not code-signed or notarized (no Apple developer certificate). Download it only from the official
  GitHub releases and check the SHA-256 checksum published with each release.
- `curl … | bash` runs a script from the internet. You can download and read `install.sh` first.
- Sentinel reads text from news feeds. A crafted headline could try to make it block or allow a trade. Its answers
  are limited to probabilities that the strategy turns into "allow", "block" and at most 3× leverage, so the worst
  case is a skipped trade or, with AI leverage on, a higher-leverage trade within the normal limits.
