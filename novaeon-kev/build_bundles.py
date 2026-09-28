"""Group collected headlines into Kev inputs shaped exactly like the live strategy's request.

Live (BreakoutRegimeKev._assess): state = {"coin": "LINK (chainlink)", "recent_headlines": [{title, summary, age_h}]},
questions = major_negative (noul) + outlook (choice), same instructions/criteria text as below.
Output: data/bundles.jsonl  {id, coin, state, questions(without labels), window_end}
"""
import json
import random
from collections import defaultdict
from datetime import datetime, timedelta

random.seed(7)
NAMES = {"BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana", "BNB": "bnb", "XRP": "xrp", "ADA": "cardano",
         "DOGE": "dogecoin", "AVAX": "avalanche", "LINK": "chainlink", "NEAR": "near protocol", "ZEC": "zcash",
         "ONDO": "ondo", "ENA": "ethena", "LTC": "litecoin", "TAO": "bittensor", "SUI": "sui", "UNI": "uniswap",
         "ARB": "arbitrum", "WLD": "worldcoin", "AAVE": "aave"}


def questions(coin: str) -> dict:
    """Identical wording to user_data/strategies/BreakoutRegimeKev.py (keep in sync)."""
    return {
        "major_negative": {
            "type": "noul",
            "instructions": f"Do these headlines report a major negative event specifically for {coin} "
                            "that makes buying it now dangerous?",
            "criteria": {
                "true": "Hack or exploit, delisting, regulatory action or lawsuit against it, insolvency, "
                        "chain halt, founder arrest, or a large coordinated sell-off of this coin.",
                "false": "Neutral or positive news, general market commentary, price analysis, or news "
                         "that only mentions the coin in passing.",
            },
        },
        "outlook": {
            "type": "choice",
            "instructions": f"Overall, how do these headlines bear on {coin} specifically over the next few days?",
            "criteria": {
                "clearly_positive": f"Concrete, material good news for {coin} itself: major adoption or "
                                    "partnership, ETF or listing approval, strong inflows, upgrade shipped.",
                "neutral_or_mixed": "Routine news, price commentary, mixed signals, or the coin is only "
                                    "mentioned in passing.",
                "negative": f"Material bad news or risk for {coin}.",
            },
        },
    }


rows = [json.loads(line) for line in open("data/headlines.jsonl")]
by_coin = defaultdict(list)
for r in rows:
    if r.get("published"):
        r["ts"] = datetime.fromisoformat(r["published"])
        by_coin[r["coin"]].append(r)

bundles = []
for coin, items in by_coin.items():
    items.sort(key=lambda r: r["ts"])
    risky = [r for r in items if any(k in r["query"] for k in ("hack", "delisting"))]
    anchors = random.sample(items, min(45, len(items))) + random.sample(risky, min(20, len(risky)))
    seen = set()
    for a in anchors:
        end = a["ts"]
        window = [r for r in items if end - timedelta(hours=72) <= r["ts"] <= end]
        k = random.choice([1, 2, 3, 4, 6, 8])
        pick = [a] + random.sample([r for r in window if r is not a], min(k - 1, len(window) - 1))
        key = (coin, tuple(sorted(p["title"] for p in pick)))
        if key in seen:
            continue
        seen.add(key)
        heads = [{"title": p["title"], "summary": "", "age_h": round((end - p["ts"]).total_seconds() / 3600, 1)}
                 for p in sorted(pick, key=lambda p: p["ts"], reverse=True)]
        bundles.append({"id": f"{coin}-{len(bundles):04d}", "coin": coin, "window_end": end.isoformat(),
                        "state": {"coin": f"{coin} ({NAMES[coin]})", "recent_headlines": heads},
                        "questions": questions(coin)})

random.shuffle(bundles)
with open("data/bundles.jsonl", "w") as f:
    for b in bundles:
        f.write(json.dumps(b) + "\n")
print("bundles", len(bundles), "coins", len(by_coin))
