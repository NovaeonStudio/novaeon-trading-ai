# Novaeon Sentinel 9B

Sentinel is the model that reads crypto headlines before the bot buys a coin. It blocks purchases on serious bad
news and, if you turn on AI leverage, it can raise leverage on clearly good news.

- Weights: [NovaeonStudio/novaeon-sentinel-9b](https://huggingface.co/NovaeonStudio/novaeon-sentinel-9b)
  (Apache-2.0), with a Mac build in 8-bit and 4-bit (MLX) and the LoRA adapter.
- Code: [`novaeon-kev/`](../novaeon-kev/) (data pipeline, labeling guide, evaluation, MLX build and serving).
- Model card: [`novaeon-kev/sentinel/MODEL_CARD.md`](../novaeon-kev/sentinel/MODEL_CARD.md).

The pipeline directory is still called `novaeon-kev/` because the model was developed as "Novaeon Kev 9B Crypto"
before it was renamed.

## How it works

Sentinel is a *decision model*, not a chat model. It is a fine-tune of
[Kev-9B](https://huggingface.co/jaredpalmer/kev-9b) by Jared Palmer, which puts a LoRA adapter and a small "pointer
head" on [Qwen3.5-9B-Base](https://huggingface.co/Qwen/Qwen3.5-9B-Base). The input is one document (the *state*)
plus typed questions; the output is a probability distribution per question, computed in one forward pass. It
generates no text, so it cannot ramble, refuse or invent a reason.

The bot sends this request (see `_assess` in [`BreakoutRegimeKev.py`](../bot/strategies/BreakoutRegimeKev.py)):

```json
{
  "state": {
    "coin": "SUI (sui)",
    "recent_headlines": [{"title": "…", "summary": "first 200 characters", "age_h": 2.0}]
  },
  "questions": {
    "major_negative": {
      "type": "noul",
      "instructions": "Do these headlines report a major negative event specifically for SUI that makes buying it now dangerous?",
      "criteria": {
        "true": "Hack or exploit, delisting, regulatory action or lawsuit against it, insolvency, chain halt, founder arrest, or a large coordinated sell-off of this coin.",
        "false": "Neutral or positive news, general market commentary, price analysis, or news that only mentions the coin in passing."
      }
    },
    "outlook": {
      "type": "choice",
      "instructions": "Overall, how do these headlines bear on SUI specifically over the next few days?",
      "criteria": {
        "clearly_positive": "Concrete, material good news for SUI itself: major adoption or partnership, ETF or listing approval, strong inflows, upgrade shipped.",
        "neutral_or_mixed": "Routine news, price commentary, mixed signals, or the coin is only mentioned in passing.",
        "negative": "Material bad news or risk for SUI."
      }
    }
  }
}
```

The answer is typed:

```json
{"answers": {
  "major_negative": {"noul": 0.04},
  "outlook": {"probabilities": {"clearly_positive": 0.12, "neutral_or_mixed": 0.81, "negative": 0.07}}
}}
```

The bot turns these into actions:

| Output | Threshold | Action |
|---|---|---|
| `major_negative` | ≥ 0.30 | Block the purchase |
| `outlook.clearly_positive` | ≥ 0.50 | 2× leverage (only with AI leverage on and no block) |
| `outlook.clearly_positive` | ≥ 0.75 and BTC ≥ 5% above its 50-day EMA | 3× leverage (same conditions) |
| anything else, no headlines, or no answer | | 1×, allowed |

The thresholds were chosen on the held-out set, not by hand (see [Choosing the thresholds](#choosing-the-thresholds)).

## Training data

We publish the pipeline, the labeling guide and the metrics. **We do not publish the raw dataset** (the headlines
belong to their publishers, and the labels are one model's reading of our guide, not ground truth).

1. **Collect** (`collect.py`, `collect2.py`): public Google News RSS searches per coin, politely rate-limited
   (one request every 2.5 s). Round 1 used five search angles per coin (plain, hacks, legal trouble, adoption,
   price moves): 7,696 headlines. Round 2 searched month by month over the previous 12 months, plus extra angles
   (token unlocks, whale sell-offs, regulators, upgrades, inflows): 25,813 more. Titles only; no article bodies,
   no prices, no personal data.
2. **Bundle** (`build_bundles.py`, `build_bundles_v2.py`): group headlines into inputs shaped exactly like the live
   request: one coin, 1 to 15 headlines with their age in hours, filtered with the same coin-name/ticker rule the
   bot uses. 2,676 items (1,258 + 1,418), from all 20 coins. About 75% of them are from 2026, 16% from 2025, the
   rest older; the newest are from 2026-09-26.
3. **Label** (`LABELING.md`, `label_schema.json`): a large language model (the "teacher") labeled every item in batches,
   following the written [labeling guide](../novaeon-kev/LABELING.md). Every batch was validated (ids, order,
   allowed values, schema) and spot-checked against evidence quotes from the source headlines. The guide is
   deliberately conservative: price predictions, "could crash" speculation and passing mentions are not bad news;
   when unsure between "clearly positive" and "neutral", choose neutral.
4. **Split** (`build_train.py`, `build_train_v2.py`): about 18% of items are held out by a SHA-256 hash of their id,
   before any training. Test set A: 248 items from round 1 (19 bad-news items). Test set B: 247 items from round 2,
   shaped like live requests (9 bad-news items). Training: 2,181 items (115 bad news; outlook 334 clearly
   positive, 203 negative, 1,644 neutral or mixed).
5. **Upweight bad news** (`build_train_v3.py`): the training tool has no per-example weights, so bad-news items are
   repeated 4 times (2,526 training records, 18.2% bad news instead of 5.3%). Missing a hack costs more than
   skipping a breakout.

## Training

A delta fine-tune that starts from Kev-9B's LoRA and continues training it on the two questions the bot asks:

```bash
# in a checkout of https://github.com/jaredpalmer/kev
python -m kev.train --data data/train-v3-2q.jsonl --init_from jaredpalmer/kev-9b \
  --base Qwen/Qwen3.5-9B-Base --out runs/novaeon-sentinel-9b \
  --epochs 2 --lr 3e-5 --lora 16 --accum 8 --batch 1 --head_lr 0 --max_state 704 \
  --device mps --dtype fp32 --weights_dtype bf16 --seed 1
```

| Setting | Value |
|---|---|
| Starting point | `jaredpalmer/kev-9b` at revision `2629c06a` (base `Qwen/Qwen3.5-9B-Base` at `68c46c4b`) |
| Adapter | LoRA r=16, alpha 32, dropout 0.05, on all attention, MLP and DeltaNet projections |
| Pointer head | Kev-9B's head, kept frozen (`--head_lr 0`) |
| Schedule | 2 epochs, learning rate 3e-5, gradient accumulation 8, 632 optimizer steps |
| Hardware | One Apple M5 Max (Metal), 4.25 hours, peak about 16.7 GB of GPU memory |

## Evaluation

All numbers are on held-out items the model never saw in training. "Bad news" = `major_negative` is true in the
teacher labels.

### Against the untuned Kev-9B (test set A, 248 items, 19 bad news, block threshold 0.6 for both)

| | Kev-9B (untuned) | Sentinel 9B |
|---|---|---|
| Bad news caught | 18 of 19 | 14 of 19 |
| Harmless items flagged as bad news | 26 | 4 |
| Precision of the bad-news flag | 0.41 | 0.78 |
| Brier score of the bad-news probability (lower is better) | 0.117 | 0.027 |
| Outlook accuracy | 0.71 | 0.92 |
| Precision of "clearly positive" (the leverage signal) | 0.41 (79 calls) | 0.83 (40 calls) |

Untuned Kev-9B flags too much as dangerous and calls "clearly positive" far too often. At the stricter 0.6 threshold
Sentinel misses more bad news, which is why the bot uses 0.30 (next table).

### At the bot's thresholds (both test sets, 495 items, 28 bad news)

| | Sentinel 9B |
|---|---|
| Bad news caught (block at ≥ 0.30) | 24 of 28 |
| Harmless items blocked | 6 of 467 (1.3%) |
| Brier score of the bad-news probability | 0.020 |
| Outlook accuracy | 0.90 |
| 2× signal (clearly positive ≥ 0.50) | 76 calls, 80% correct |
| 3× signal | no threshold reached 90% precision; kept at ≥ 0.75 plus the Bitcoin condition, so 3× is rare |

### Choosing the thresholds

`select_best.py` pools both test sets and sweeps the block threshold from 0.05 to 0.95. Cost = 3 × missed bad news +
1 × harmless item blocked (a missed hack costs more than a skipped breakout); lowest cost wins. For leverage it takes
the smallest `clearly_positive` probability whose calls are at least 80% correct (2×) or 90% correct (3×) over at
least 8 calls. Result: block at 0.30 (cost 18), 2× at 0.50. The same procedure also compared two earlier training
runs; this one had the lowest cost.

### Extra questions (not used by the bot)

Test set B also has four questions Sentinel was not trained on (event type, impact 0–4, relevance, staleness). The
zero-shot results are in `novaeon-kev/results/v3-r2.json` (for example event type accuracy 0.73, impact within one
step 0.97). They are not used for trading.

## Running on your Mac: 8-bit and 4-bit

`novaeon-kev/sentinel/build_mlx.py` merges the LoRA into Qwen3.5-9B-Base exactly as the serving path does, drops the
vision tower and the language-model head (Sentinel only reads hidden states), and quantizes the linear layers with
MLX. `sentinel/serve.py` serves the result with Kev's server, same `/v1/systemone` API.

`sentinel/parity.py` sends all 495 held-out items to the reference model (bf16 base with the LoRA merged at load)
and to a build, answer by answer, at the bot's thresholds:

| Build | Download | Bad news caught | Harmless blocked | Outlook accuracy | 2× calls | 2× correct | Block decisions that differ from reference |
|---|---|---|---|---|---|---|---|
| Reference (bf16) | not shipped | 24 / 28 | 6 | 0.901 | 76 | 80.3% | – |
| **MLX 8-bit** (16 GB+ Macs) | 8.4 GB | 23 / 28 | 8 | 0.911 | 74 | 82.4% | 3 of 495 |
| MLX 4-bit, plain, group 64 (not shipped) | 4.5 GB | 25 / 28 | 12 | 0.885 | 84 | 73.8% | 7 of 495 |
| **MLX 4-bit, distilled (DWQ)** (8 GB Macs) | 4.5 GB | 23 / 28 | 6 | 0.893 | 91 | 72.5% | 6 of 495 (vs 8-bit) |

- **8-bit is on par with the reference.** Mean change of the bad-news probability: 0.002.
- **Plain 4-bit leans cautious**: it blocks twice as many harmless items. The shipped 4-bit build is **distilled**
  (DWQ, `sentinel/dwq_sentinel.py`): its quantization scales were tuned so its hidden states match the full model on
  training data (never on the test set). Its news filter matches the reference (23 of 28 caught, 6 harmless blocked),
  but its 2× signal is less precise (72.5%). That is why 8 GB Macs get it **with AI leverage locked off**: only the
  news filter is used there, and that part is on par.
- Memory: the 4-bit build uses about 5 GB while idle; with 495 checks sent back to back it peaked at about 7.6 GB.
  The bot sends a check only right before a purchase.
- Speed on an Apple M5 Max: about 0.5 s per check for either build. Not yet measured on a base 8 GB M1/M2.

## Running on Linux: NVIDIA GPU or CPU (experimental), or on another machine

Off the Mac there is no MLX build. The installer's `cuda` and `cpu` modes serve the **LoRA run** from Hugging Face
(`lora/`: adapter, pointer head, tokenizer) on top of its base model `Qwen/Qwen3.5-9B-Base` (pinned to the snapshot
Sentinel was trained on) with Kev's PyTorch backend, via the same `sentinel/serve.py`:

```bash
SENTINEL_DEVICE=cuda python -m sentinel.serve --run <lora dir> --port 8010   # or SENTINEL_DEVICE=cpu
```

- This is the reference path of the table above (bf16, adapter kept unmerged as trained), not a quantized build.
- `SENTINEL_DEVICE` forces the device (Kev otherwise picks cuda, then mps, then cpu); Kev's `KEV_*` options apply
  (`KEV_CUDA_GRAPHS`, `KEV_FUSED`, `KEV_DTYPE`, ...). The installer writes its choices to
  `~/NovaeonTradingAI/sentinel/sentinel.env`; your own go into `sentinel/sentinel.local.env` next to it.
- **NVIDIA GPU (`cuda`):** the bf16 backbone is about 17 GB, so a 24 GB GPU is the minimum. Kev's CUDA serving
  defaults (CUDA graphs with several GB of fixed buffers, fused Triton kernels) are used where they fit: CUDA graphs
  only on GPUs with 30 GB or more, the flash-linear-attention kernels only when a C compiler is installed (Triton
  compiles at run time). The model is staged through main memory while it loads (about 20 GB). What we tested: the
  installer end to end on Ubuntu 26.04 with an NVIDIA GTX 1650 Ti (driver 595, PyTorch 2.8 cu129 chosen
  automatically), and this serving code on that GPU with the small Kev-0.8B model (eager, bf16: about 80 ms per
  check). The 9B model itself has not run on an NVIDIA GPU yet.
- **CPU (`cpu`):** needs about 20 GB of main memory. It works, but it is **not recommended**: PyTorch reaches about
  90 GFLOPS in bf16 on a 6-core AVX2 laptop CPU (435 GFLOPS in fp32), which puts one news check with 15 headlines at
  roughly 1 to 3 minutes. The installer lets the engine wait up to 240 s in this mode. CPUs with AMX or AVX512-BF16
  are much faster; not measured.
- **Another machine (`remote`):** the engine asks a Sentinel on another machine, usually a Mac in the same Tailscale
  network. Measured from a Linux server to a Mac (8-bit build) over Tailscale: about 0.2 s per check, the same
  answers as on the Mac. See the README, "Split setup".

## Limitations

- **English crypto headlines only.** Other languages and other asset classes are out of scope.
- **Teacher labels, not outcomes.** Sentinel learned one model's reading of a written guide. It does not predict
  prices or returns, and the labels can be wrong.
- **Small bad-news sample.** The held-out sets contain 28 bad-news items; the confidence intervals are wide.
- **Time-limited knowledge.** Most training items are from 2025–2026. New kinds of events, new coins or new slang
  may be judged worse.
- **Headlines, not articles.** A misleading headline can mislead the model.
- **The 20 coins.** Training covered the bot's 20 coins; other coins work through the same questions but were not
  tested.
- **Failure mode is fail-open.** If Sentinel is down, the bot trades at 1× without the check.

## Reproducing

1. Install Kev: `git clone https://github.com/jaredpalmer/kev && cd kev && uv sync`. Run the scripts below with Kev's
   Python from the `novaeon-kev/` folder; if Kev is not installed in that environment, set `KEV_DIR=/path/to/kev`.
2. Collect and bundle headlines: `python collect.py`, `python collect2.py`, `python build_bundles.py`,
   `python build_bundles_v2.py` (takes hours because of the rate limit; your headlines will differ from ours).
3. Label with any capable model following `LABELING.md` and `label_schema.json`, then build the split:
   `python build_train.py`, `python build_train_v2.py`, `python build_train_v3.py`.
4. Train with the command above (a 9B fine-tune needs a Mac or GPU with about 32 GB of memory or more).
5. Serve and evaluate: `python -m kev.serve --run runs/novaeon-sentinel-9b --port 8011`, then
   `python evaluate.py http://127.0.0.1:8011 data/heldout.jsonl out.json` and
   `python evaluate6.py http://127.0.0.1:8011 data/heldout-r2.jsonl out-r2.json`, and `select_best.py` for thresholds.
6. Build and check the Mac packages: `python sentinel/build_mlx.py runs/novaeon-sentinel-9b out-q8 --bits 8`
   (or `--bits 4 --group 64`), `python -m sentinel.serve --run out-q8 --port 8012`, then
   `python sentinel/parity.py http://127.0.0.1:8011 http://127.0.0.1:8012 parity.json`.

To evaluate our published weights on your own labeled items, start at step 5.
