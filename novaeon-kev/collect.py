"""Collect dated crypto headlines per coin from Google News RSS (polite: 1 request / 2.5 s).
Output: data/headlines.jsonl  {coin, query, title, source, published(ISO), link}"""
import json, time, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
COINS = {"BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana", "BNB": "BNB binance coin", "XRP": "XRP ripple",
         "ADA": "cardano", "DOGE": "dogecoin", "AVAX": "avalanche AVAX", "LINK": "chainlink", "NEAR": "NEAR protocol",
         "ZEC": "zcash", "ONDO": "ondo finance", "ENA": "ethena", "LTC": "litecoin", "TAO": "bittensor",
         "SUI": "sui blockchain", "UNI": "uniswap", "ARB": "arbitrum", "WLD": "worldcoin", "AAVE": "aave"}
ANGLES = ["{n}", "{n} hack OR exploit OR stolen", "{n} delisting OR lawsuit OR SEC OR investigation",
          "{n} partnership OR ETF OR adoption OR launch", "{n} price crash OR rally"]
seen, out = set(), open("data/headlines.jsonl", "w")
for coin, name in COINS.items():
    for angle in ANGLES:
        q = angle.format(n=name)
        url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": q, "hl": "en-US", "gl": "US", "ceid": "US:en"})
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            root = ET.fromstring(urllib.request.urlopen(req, timeout=25).read())
        except Exception as e:  # noqa: BLE001
            print("fail", coin, q, e, flush=True); time.sleep(5); continue
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
        print(f"{coin:5} {q[:55]:55} +{n}", flush=True)
        time.sleep(2.5)
out.close()
print("done", len(seen))
