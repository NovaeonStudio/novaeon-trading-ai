"""Round-2 bundles from data/headlines-v2.jsonl, shaped like what the live bot sends:
only headlines the strategy's coin filter would match (name case-insensitive, ticker uppercase), 1-15 per bundle
from a 72 h window, six questions (questions_v2). Round-1 held-out stays untouched (these are all new headlines).
Output: data/bundles-v2.jsonl + data/batch-21.. (60 items each, same line format as round 1)."""
import json
import random
import re
from collections import defaultdict
from datetime import datetime, timedelta

from questions_v2 import questions

random.seed(21)
N_TARGET = 1500
NAMES = {  # identical to BreakoutRegimeKev.NAMES (live filter)
    "BTC": ["bitcoin"], "ETH": ["ethereum", "ether"], "SOL": ["solana"], "BNB": ["bnb"],
    "XRP": ["xrp", "ripple"], "ADA": ["cardano"], "DOGE": ["dogecoin"], "AVAX": ["avalanche"],
    "LINK": ["chainlink"], "NEAR": ["near protocol"], "ZEC": ["zcash"], "ONDO": ["ondo"], "ENA": ["ethena"],
    "LTC": ["litecoin"], "TAO": ["bittensor"], "SUI": ["sui"], "UNI": ["uniswap"], "ARB": ["arbitrum"],
    "WLD": ["worldcoin"], "AAVE": ["aave"],
}


def live_match(coin: str, title: str) -> bool:
    by_name = re.compile(r"\b(" + "|".join(map(re.escape, NAMES[coin])) + r")\b", re.I)
    return bool(by_name.search(title) or re.search(r"\b" + re.escape(coin) + r"\b", title))


by_coin = defaultdict(list)
for r in map(json.loads, open("data/headlines-v2.jsonl")):
    if r.get("published") and live_match(r["coin"], r["title"]):
        r["ts"] = datetime.fromisoformat(r["published"])
        by_coin[r["coin"]].append(r)

per_coin = N_TARGET // len(by_coin)
bundles, seen = [], set()
for coin, items in sorted(by_coin.items()):
    items.sort(key=lambda r: r["ts"])
    risky = [r for r in items if re.search(r"hack|exploit|delist|lawsuit|outage|halt|unlock|dump|ban|probe", r["query"])]
    upside = [r for r in items if re.search(r"ETF|partnership|listing|launch|upgrade|inflows|mainnet", r["query"])]
    anchors = (random.sample(items, min(per_coin // 2, len(items))) + random.sample(risky, min(per_coin // 4, len(risky)))
               + random.sample(upside, min(per_coin // 4, len(upside))))
    for a in anchors:
        end = a["ts"]
        window = [r for r in items if end - timedelta(hours=72) <= r["ts"] <= end and r is not a]
        k = random.choice([1, 2, 3, 4, 5, 6, 8, 10, 12, 15])
        pick = [a] + random.sample(window, min(k - 1, len(window)))
        key = (coin, tuple(sorted(p["title"] for p in pick)))
        if key in seen:
            continue
        seen.add(key)
        heads = [{"title": p["title"], "summary": "", "age_h": round((end - p["ts"]).total_seconds() / 3600, 1)}
                 for p in sorted(pick, key=lambda p: p["ts"], reverse=True)]
        name = NAMES[coin][0]
        bundles.append({"id": f"{coin}-v2-{len(bundles):04d}", "coin": coin, "window_end": end.isoformat(),
                        "state": {"coin": f"{coin} ({name})", "recent_headlines": heads},
                        "questions": questions(f"{coin} ({name})")})

random.shuffle(bundles)
with open("data/bundles-v2.jsonl", "w") as f:
    for b in bundles:
        f.write(json.dumps(b, ensure_ascii=False) + "\n")
for i in range(0, len(bundles), 60):
    n = 21 + i // 60
    with open(f"data/batch-{n:02d}.txt", "w") as f:
        for b in bundles[i:i + 60]:
            hs = " || ".join(f"[{h['age_h']:.0f}h] {h['title']}" for h in b["state"]["recent_headlines"])
            f.write(f"{b['id']} | coin {b['state']['coin']} | {hs}\n")
print("matched headlines", sum(map(len, by_coin.values())), "bundles", len(bundles),
      "batches", f"21..{21 + (len(bundles) - 1) // 60}",
      "mean headlines", round(sum(len(b["state"]["recent_headlines"]) for b in bundles) / len(bundles), 1))
