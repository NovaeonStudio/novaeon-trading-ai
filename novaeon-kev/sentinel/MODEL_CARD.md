---
license: apache-2.0
base_model: jaredpalmer/kev-9b
base_model_relation: finetune
library_name: mlx
pipeline_tag: text-classification
language:
  - en
tags:
  - mlx
  - decision-model
  - kev
  - crypto
  - news-classification
  - trading
  - lora
  - qwen3.5
  - apple-silicon
  - novaeon
---

# Novaeon Sentinel 9B

![Novaeon Sentinel 9B: reads the news before your bot buys](https://huggingface.co/NovaeonStudio/novaeon-sentinel-9b/resolve/main/assets/sentinel-banner.png)


**A 9B model that reads crypto headlines and answers in probabilities, not prose. It runs on any Apple Silicon Mac,
including 8 GB machines.**

Sentinel is the news judge inside [NovaeonTradingAI](https://github.com/NovaeonStudio/novaeon-trading-ai), an
open-source trading bot. Before the bot opens a position it asks Sentinel two typed questions about the coin's
headlines from the last 48 hours. Sentinel answers each with a probability distribution in one forward pass: no
generated text, no refusals, no invented reasons. The bot blocks the purchase on serious bad news and, if the user
enables it, raises leverage on clearly good news.

It is a fine-tune of [Kev-9B](https://huggingface.co/jaredpalmer/kev-9b) by Jared Palmer, a decision model built on
[Qwen3.5-9B-Base](https://huggingface.co/Qwen/Qwen3.5-9B-Base), and keeps Kev's interface (the `/v1/systemone`
request shape served by [`kev.serve`](https://github.com/jaredpalmer/kev)).

> Not financial advice. Sentinel judges headlines; it does not predict prices. See [Limitations](#limitations).

## What's in this repository

| Folder | What | Size | For |
|---|---|---|---|
| `mlx-8bit/` | Merged model, text backbone only, 8-bit MLX + pointer head + tokenizer | 8.4 GB | Macs with 16 GB or more; matches the full model |
| `mlx-4bit/` | Same, 4-bit (group size 64), distilled (DWQ) | 4.5 GB | Macs with 8 GB; news filter on par, 2× signal weaker (see parity) |
| `lora/` | LoRA adapter + pointer head for `kev.serve` on top of Qwen3.5-9B-Base | 0.2 GB | GPUs, research, further fine-tuning |

The MLX builds drop Qwen's vision tower and language-model head (Sentinel only reads hidden states), so they load
nothing that is not used. The pointer head is stored as `head.pt` (a PyTorch state dict, as in Kev).


## The two questions

| Key | Type | Question | Output |
|---|---|---|---|
| `major_negative` | `noul` (yes/no) | Do these headlines report a major negative event specifically for this coin that makes buying it now dangerous? (hack or exploit, delisting, regulatory action or lawsuit, insolvency, chain halt, founder arrest, large coordinated sell-off) | P(yes) |
| `outlook` | `choice` | Overall, how do these headlines bear on this coin over the next few days? | P over `clearly_positive`, `neutral_or_mixed`, `negative` |

The exact instruction and criteria texts are in
[`BreakoutRegimeKev.py`](https://github.com/NovaeonStudio/novaeon-trading-ai/blob/main/bot/strategies/BreakoutRegimeKev.py).
Sentinel was trained with exactly these texts; other wordings work through Kev's general ability but were not
evaluated.

### How NovaeonTradingAI uses the outputs

| Output | Threshold | Action |
|---|---|---|
| `major_negative` | ≥ 0.30 | Block the purchase |
| `outlook.clearly_positive` | ≥ 0.50 | 2× leverage (opt-in, never on 8 GB Macs) |
| `outlook.clearly_positive` | ≥ 0.75 and BTC ≥ 5% above its 50-day EMA | 3× leverage (opt-in) |
| otherwise, or no answer | | 1× |

Thresholds were selected on the held-out set: the block threshold minimizes 3 × missed bad news + 1 × harmless items
blocked; the 2× threshold is the lowest with at least 80% precision. No threshold reached 90% precision for 3×, so
3× stays deliberately rare.

## Results

All results are on held-out items that were split off by a hash of their id before training. Labels come from a
teacher model following a written guide (see [Training data](#training-data)).

### Sentinel vs. the untuned Kev-9B (test set A: 248 items, 19 bad news; threshold 0.6 for both)

| | Kev-9B | **Sentinel 9B** |
|---|---|---|
| Bad news caught | 18 / 19 | 14 / 19 |
| Harmless items flagged as bad news | 26 | **4** |
| Bad-news precision | 0.41 | **0.78** |
| Bad-news Brier score (lower is better) | 0.117 | **0.027** |
| Outlook accuracy | 0.71 | **0.92** |
| "Clearly positive" precision | 0.41 (79 calls) | **0.83** (40 calls) |

At 0.6 Sentinel is too strict, which is why the bot blocks at 0.30:

### At the bot's thresholds (test sets A + B: 495 items, 28 bad news)

| | Sentinel 9B |
|---|---|
| Bad news caught (P ≥ 0.30) | **24 / 28** |
| Harmless items blocked | **6 / 467** (1.3%) |
| Bad-news Brier score | 0.020 |
| Outlook accuracy | 0.90 |
| 2× signal (P(clearly positive) ≥ 0.50) | 76 calls, **80.3%** correct |

### Parity of the MLX builds (same 495 items, answer by answer against the bf16 reference)

| Build | Bad news caught | Harmless blocked | Outlook acc. | 2× calls | 2× precision | Block decisions changed | Mean abs. change of P(bad news) |
|---|---|---|---|---|---|---|---|
| Reference (bf16, LoRA merged at load) | 24 / 28 | 6 | 0.901 | 76 | 0.803 | – | – |
| **`mlx-8bit`** | 23 / 28 | 8 | 0.911 | 74 | 0.824 | 3 | 0.002 |
| `4-bit plain` (not shipped) | 25 / 28 | 12 | 0.885 | 84 | 0.738 | 7 | 0.020 |
| **`mlx-4bit`** (DWQ) | 23 / 28 | 6 | 0.893 | 91 | 0.725 | 6 (vs 8-bit) | 0.011 (vs 8-bit) |

The 8-bit build is on par with the reference. A plain 4-bit build blocks twice as many harmless items; the shipped
`mlx-4bit` is distilled (DWQ: quantization scales tuned to match the full model's hidden states on training data), and
its news filter is on par with the reference. Its 2× signal is less precise, so NovaeonTradingAI uses it on 8 GB Macs
with AI leverage locked off. Memory for `mlx-4bit`: about 5 GB idle; about 7.6 GB peak with 495 checks back to back. Speed on an Apple M5 Max: about 0.5 s
per request for either build.

### What the veto did to the bot (replay over a year of trades)

Agreement with teacher labels is not the same as being useful for trading, so we also replayed the bot's news check
over a year of backtest entries (Binance perpetuals, 2025-10-01 to 2026-09-23, 20 coins, 1×, fees and funding
included), with archived headlines instead of the live feeds. Date-only timestamps count as known 24 hours later.

| | Entries | Avg. trade | Winners | 72 h after entry |
|---|---|---|---|---|
| Blocked by Sentinel (P ≥ 0.30) | 10 | −2.1% | 1 of 10 | −2.8% |
| Allowed | 606 | +1.0% | 38% | +0.9% |

Blocked entries did worse (−3.0 points per trade, one-sided permutation p ≈ 0.05), but the 10 blocks come from about
five events, so this is weak evidence. The portfolio result was unchanged (+61.4% with the news check, +61.5%
without; the strategy's stop-loss already limits these trades). Read: a guard against hack-type events, not a source
of returns. Code and details: [research/veto-eval](https://github.com/NovaeonStudio/novaeon-trading-ai/tree/main/research/veto-eval).

### Extra questions (not trained, not used by the bot)

On test set B we also asked four questions Sentinel was not trained on. Zero-shot: event type (10 classes)
accuracy 0.73, impact (0–4) within one step 0.97, "is this about the coin" accuracy 0.83.

## Use

### On a Mac (MLX)

```bash
git clone https://github.com/jaredpalmer/kev && (cd kev && uv sync)
git clone https://github.com/NovaeonStudio/novaeon-trading-ai
huggingface-cli download NovaeonStudio/novaeon-sentinel-9b --include "mlx-8bit/*" --local-dir sentinel
# mlx-4bit/* on a Mac with 8 GB

cd kev && PYTHONPATH=../novaeon-trading-ai/novaeon-kev uv run python -m sentinel.serve \
  --run ../sentinel/mlx-8bit --port 8010
```

### With the LoRA (any machine that runs Kev)

```bash
huggingface-cli download NovaeonStudio/novaeon-sentinel-9b --include "lora/*" --local-dir sentinel
cd kev && uv run python -m kev.serve --run ../sentinel/lora --port 8010
```

### Ask

```bash
curl -s localhost:8010/v1/systemone -H 'content-type: application/json' -d '{
  "state": {"coin": "SUI (sui)", "recent_headlines": [
    {"title": "Sui Network stalls: mainnet halted for hours, validators investigating", "summary": "", "age_h": 2.0}]},
  "questions": {
    "major_negative": {"type": "noul",
      "instructions": "Do these headlines report a major negative event specifically for SUI that makes buying it now dangerous?"},
    "outlook": {"type": "choice",
      "instructions": "Overall, how do these headlines bear on SUI specifically over the next few days?",
      "criteria": {"clearly_positive": "Concrete, material good news for SUI itself.",
                   "neutral_or_mixed": "Routine news, price commentary, mixed signals, or only a passing mention.",
                   "negative": "Material bad news or risk for SUI."}}}}'
```

The response contains `answers.major_negative.noul` (a probability) and `answers.outlook.probabilities`.

## Training data

We publish the pipeline, the labeling guide and the metrics, not the raw dataset.

- **Sources:** public Google News RSS search results for the bot's 20 coins (BTC, ETH, SOL, BNB, XRP, ADA, DOGE,
  AVAX, LINK, NEAR, ZEC, ONDO, ENA, LTC, TAO, SUI, UNI, ARB, WLD, AAVE), collected in two rounds (7,696 and 25,813
  headlines), with search angles for plain news, hacks, legal trouble, adoption, token unlocks and sell-offs. Titles
  only: no article bodies, no prices, no personal data.
- **Items:** 2,676 inputs of 1 to 15 headlines about one coin, shaped exactly like the bot's live requests.
  About 75% are from 2026 and 16% from 2025; the newest are from 2026-09-26.
- **Labels:** teacher labels from a large language model following a fixed written
  [labeling guide](https://github.com/NovaeonStudio/novaeon-trading-ai/blob/main/novaeon-kev/LABELING.md); every
  batch validated and spot-checked against evidence quotes. The guide is conservative: speculation, price
  predictions and passing mentions are not bad news.
- **Split:** about 18% held out by id hash (495 items: test set A, 248 from round 1; test set B, 247 live-shaped
  from round 2). Training: 2,181 items, of which 115 bad news; bad-news items repeated 4× (2,526 records).

## Training

Delta fine-tune from Kev-9B (revision `2629c06a`, base Qwen3.5-9B-Base revision `68c46c4b`) with `kev.train`:
LoRA r=16 (alpha 32, dropout 0.05) on all attention, MLP and Gated DeltaNet projections, Kev's pointer head frozen,
2 epochs, learning rate 3e-5, gradient accumulation 8, 632 optimizer steps, fp32 compute with bf16 weights. One
Apple M5 Max, 4.25 hours. MLX builds: LoRA merged into the base, then linear layers quantized with MLX (8-bit and
4-bit, group size 64). Full commands:
[docs/SENTINEL.md](https://github.com/NovaeonStudio/novaeon-trading-ai/blob/main/docs/SENTINEL.md).

## Intended use

- Screening English crypto news headlines for coin-specific danger (hacks, delistings, legal action, outages)
  before an automated or manual trade.
- A conservative "clearly good news" signal, meant to be combined with other conditions, never used alone.
- Research on small decision models and their quantization on consumer hardware.

**Out of scope:** predicting prices or returns; financial advice; judging people; non-crypto or non-English text;
any use where a missed warning could cause harm that a human does not review.

## Limitations

- **Teacher labels, not outcomes.** Sentinel reproduces one model's reading of our guide. The labels can be wrong,
  and "bad news" does not always move prices.
- **Few bad-news examples.** The test sets contain 28 bad-news items, so the numbers above have wide uncertainty.
  It missed 4 of 28 at the bot's threshold.
- **Time-limited.** Training data runs to late September 2026 and is concentrated in 2025–2026. New event types,
  new coins and new slang may be judged worse.
- **Headlines only.** Clickbait or misleading headlines can mislead it; it never reads the article.
- **Source bias.** Google News ranking decides which headlines were collected, which favors large English-language
  outlets and aggregators.
- **Coin coverage.** Trained on 20 coins. Other coins go through the same questions but were not evaluated.
- **Adversarial text.** Headlines are untrusted input. A crafted headline could push a probability either way; the
  bot limits the consequence to allowing or blocking a trade and at most 3× leverage.
- **4-bit build.** News filter on par, but a weaker 2× signal than 8-bit (see parity); AI leverage is locked on 8 GB Macs.
- **Confident outputs.** Sentinel ships without a fitted temperature (T = 1.0), and its probabilities are often
  close to 0 or 1. The Brier scores above are good, but treat a probability as a score for thresholds, not as an
  exact chance.

## License and credits

Apache-2.0, like the models it is built on:

- [Kev-9B](https://huggingface.co/jaredpalmer/kev-9b) by Jared Palmer (Apache-2.0),
- [Qwen3.5-9B-Base](https://huggingface.co/Qwen/Qwen3.5-9B-Base) by the Qwen team (Apache-2.0).

Fine-tune, data pipeline, labeling guide and MLX builds: [Novaeon Studio](https://novaeon.studio). Code:
[github.com/NovaeonStudio/novaeon-trading-ai](https://github.com/NovaeonStudio/novaeon-trading-ai) (GPL-3.0).

Formerly developed under the name "Novaeon Kev 9B Crypto".

## Citation

```bibtex
@misc{novaeon2026sentinel,
  title        = {Novaeon Sentinel 9B: a news judge for crypto trading},
  author       = {{Novaeon Studio}},
  year         = {2026},
  howpublished = {\url{https://huggingface.co/NovaeonStudio/novaeon-sentinel-9b}}
}

@misc{qwen3.5,
  title  = {{Qwen3.5}: Towards Native Multimodal Agents},
  author = {{Qwen Team}},
  month  = {February},
  year   = {2026},
  url    = {https://qwen.ai/blog?id=qwen3.5}
}
```

Please also credit Kev: [github.com/jaredpalmer/kev](https://github.com/jaredpalmer/kev).
