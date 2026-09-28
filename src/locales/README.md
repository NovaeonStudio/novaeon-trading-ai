# App languages

`en.json` (English, source and fallback), `de.json` (German), `ro.json` (Romanian). All three files must have the
same keys (a unit test checks this). Brand and product names stay untranslated: NovaeonTradingAI, novæon,
Novaeon Sentinel, Sentinel, MetaMask, Hyperliquid, USDC.

- German: informal "du", short and natural.
- Romanian: informal "tu", diacritics ă â î ș ț (comma below).

Corrections from native speakers are welcome as pull requests.

Message syntax is vue-i18n: `{name}` is a placeholder, `|` separates plural forms (Romanian may use three:
`one | few | other`), and the characters `@ { } | $` must be written as literals like `{'@'}`.
