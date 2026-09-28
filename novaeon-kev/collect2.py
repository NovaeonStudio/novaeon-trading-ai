"""Round 2 collection: more headlines per coin, month by month over the last 12 months, with extra angles.
Polite (1 request / 2.5 s). Keeps only titles not already in data/headlines.jsonl (same coin, same title).
Output: data/headlines-v2.jsonl  {coin, query, title, source, published(ISO), link}"""
import json
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from email.utils import parsedate_to_datetime

COINS = {"BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana", "BNB": "BNB binance coin", "XRP": "XRP ripple",
         "ADA": "cardano", "DOGE": "dogecoin", "AVAX": "avalanche AVAX", "LINK": "chainlink", "NEAR": "NEAR protocol",
         "ZEC": "zcash", "ONDO": "ondo finance", "ENA": "ethena", "LTC": "litecoin", "TAO": "bittensor",
         "SUI": "sui blockchain", "UNI": "uniswap", "ARB": "arbitrum", "WLD": "worldcoin", "AAVE": "aave"}
# per month: the plain coin query plus a risk and an upside angle (both classes are rare, so ask for them)
MONTHLY = ["{n} crypto", "{n} hack OR exploit OR delist OR lawsuit OR outage OR halt",
           "{n} ETF OR partnership OR listing OR launch OR upgrade"]
# once, whole year: angles round 1 did not ask for
EXTRA = ["{n} token unlock", "{n} whale sell-off OR dump", "{n} regulator OR ban OR probe",
         "{n} mainnet OR upgrade shipped", "{n} inflows OR institutional"]

seen = {(r["coin"], r["title"].lower()) for r in map(json.loads, open("data/headlines.jsonl"))}
out = open("data/headlines-v2.jsonl", "w")


def fetch(coin: str, q: str) -> int:
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": q, "hl": "en-US", "gl": "US", "ceid": "US:en"})
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        root = ET.fromstring(urllib.request.urlopen(req, timeout=25).read())
    except Exception as e:  # noqa: BLE001
        print("fail", coin, q, e, flush=True); time.sleep(10); return 0
    n = 0
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        src = (it.findtext("source") or "").strip()
        if " - " in title and src and title.endswith(src):
            title = title[: -len(src) - 3].strip()
        key = (coin, title.lower())
        if not title or key in seen:
            continue
        seen.add(key)
        try:
            pub = parsedate_to_datetime(it.findtext("pubDate")).isoformat()
        except Exception:  # noqa: BLE001
            pub = None
        out.write(json.dumps({"coin": coin, "query": q, "title": title, "source": src, "published": pub,
                              "link": it.findtext("link")}) + "\n")
        n += 1
    out.flush()
    time.sleep(2.5)
    return n


today = date.today()
months = [(today.replace(day=1) - timedelta(days=30 * i)).replace(day=1) for i in range(12)]
for coin, name in COINS.items():
    total = 0
    for angle in EXTRA:
        total += fetch(coin, angle.format(n=name))
    for m0 in months:
        m1 = (m0 + timedelta(days=32)).replace(day=1)
        for angle in MONTHLY:
            total += fetch(coin, f"{angle.format(n=name)} after:{m0.isoformat()} before:{m1.isoformat()}")
    print(f"{coin:5} +{total}", flush=True)
out.close()
print("done", flush=True)
