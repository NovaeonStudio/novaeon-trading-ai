# Veto replay: BreakoutRegimeKev in the backtester, with the live RSS feeds replaced by an archive of timestamped
# headlines (novaeon-kev data collection, Google News RSS). Everything else is the live code path: the same coin
# filter, the same Sentinel request, the same 0.30 veto threshold, 1x (AI leverage is off in backtests).
#
# REPLAY_MODE    off    = plain strategy, no news check (baseline)
#                record = ask Sentinel and log the decision, but never block (every entry the bot wanted, with its verdict)
#                veto   = block like the live bot
# REPLAY_TIMING  safe   = headlines whose timestamp is only a day (hh:00:00 at 00/07/08 UTC, i.e. midnight Pacific)
#                         count as available 24 h later, so a day-level stamp can never leak later news into an entry
#                raw    = trust the timestamps (optimistic, can leak up to a day of future news)
# REPLAY_SOURCES all | press (only CoinDesk, Cointelegraph, Decrypt, The Block: the four feeds the live bot reads)
# REPLAY_SELECT  newest = the 15 newest matching headlines (live selection up to 1.1.0)
#                live   = hits of risk-angled searches first (up to MAX_RISK_HEADLINES), then the newest (1.1.1+)
import bisect
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE.parents[1] / "user_data" / "strategies"))
if (HERE / "lib" / "BreakoutRegimeKev.py").exists():   # test a newer BreakoutRegimeKev without deploying it to the bot
    sys.path.insert(0, str(HERE / "lib"))

import BreakoutRegimeKev as K  # noqa: E402
from BreakoutRegime import BreakoutRegime  # noqa: E402
from BreakoutRegimeKev import BreakoutRegimeKev  # noqa: E402

MODE = os.environ.get("REPLAY_MODE", "record")
TIMING = os.environ.get("REPLAY_TIMING", "safe")
SOURCES = os.environ.get("REPLAY_SOURCES", "all")
SELECT = os.environ.get("REPLAY_SELECT", "newest")
TAG = os.environ.get("REPLAY_TAG", f"{MODE}-{TIMING}-{SOURCES}-{SELECT}")
RISKY = re.compile(r"hack|exploit|stolen|delist|lawsuit|SEC|investigation|outage|halt|ban|probe", re.I)
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)
LOG = OUT / f"decisions-{TAG}.jsonl"
CACHE = OUT / "sentinel-cache.jsonl"
PRESS = {"CoinDesk", "Cointelegraph", "Decrypt", "The Block"}


def _load_archive():
    seen, rows = set(), []
    for name in ("headlines.jsonl", "headlines-v2.jsonl"):
        for line in open(HERE / "data" / name):
            r = json.loads(line)
            key = r["title"].strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            if SOURCES == "press" and r.get("source") not in PRESS:
                continue
            pub = datetime.fromisoformat(r["published"])
            day_only = pub.minute == 0 and pub.second == 0 and pub.hour in (0, 7, 8)
            avail = pub + timedelta(hours=24) if (day_only and TIMING == "safe") else pub
            rows.append((avail, r["title"].strip(), bool(RISKY.search(r["query"].split(" after:")[0]))))
    rows.sort(key=lambda x: x[0])
    return [r[0] for r in rows], [r[1] for r in rows], [r[2] for r in rows]


TIMES, TITLES, RISK = _load_archive()


def _load_cache() -> dict:
    out = {}
    if CACHE.exists():
        for line in open(CACHE):
            r = json.loads(line)
            out[r["key"]] = r["res"]
    return out


class BreakoutRegimeReplay(BreakoutRegimeKev):
    _now = None
    _cache = _load_cache()

    def _news_for(self, coin: str) -> list[dict]:
        words = K.NAMES.get(coin, [coin.lower()])
        by_name = re.compile(r"\b(" + "|".join(map(re.escape, words)) + r")\b", re.I)
        by_ticker = re.compile(r"\b" + re.escape(coin) + r"\b")
        t = self._now
        hi = bisect.bisect_right(TIMES, t)
        lo = bisect.bisect_left(TIMES, t - timedelta(hours=K.HEADLINE_MAX_AGE_H))
        cand = [i for i in range(hi - 1, lo - 1, -1) if by_name.search(TITLES[i]) or by_ticker.search(TITLES[i])]
        if SELECT == "live":
            risk = [i for i in cand if RISK[i]][: K.MAX_RISK_HEADLINES]
            rest = [i for i in cand if i not in set(risk)]
            chosen = sorted(risk + rest[: K.MAX_HEADLINES - len(risk)], reverse=True)
        else:
            chosen = cand[: K.MAX_HEADLINES]
        return [{"title": TITLES[i], "summary": "", "age_h": round((t - TIMES[i]).total_seconds() / 3600, 1)}
                for i in chosen]

    def _assess(self, pair: str) -> dict:
        self._assess_cache.clear()   # the live cache is keyed on wall-clock time; replay decides per candle
        coin = pair.split("/")[0]
        news = self._news_for(coin)
        if not news:
            return {"headlines": [], "p_negative": None, "outlook": None, "error": None}
        key = hashlib.sha256(json.dumps([coin, news], sort_keys=True).encode()).hexdigest()
        hit = self._cache.get(key)
        if hit is not None:
            return {"headlines": news, **hit}
        res = super()._assess(pair)   # live request path (calls _news_for again: same list)
        keep = {"p_negative": res["p_negative"], "outlook": res["outlook"], "error": res["error"]}
        if not res["error"]:
            self._cache[key] = keep
            with CACHE.open("a") as f:
                f.write(json.dumps({"key": key, "res": keep}) + "\n")
        return {**res, "headlines": news}

    def _log(self, rec: dict) -> None:   # never touch the live decision log
        with LOG.open("a") as f:
            f.write(json.dumps({**rec, "mode": MODE, "timing": TIMING, "sources": SOURCES}) + "\n")

    def leverage(self, pair, current_time, current_rate, proposed_leverage, max_leverage, entry_tag, side, **kwargs):
        if MODE == "off":
            return BreakoutRegime.leverage(self, pair, current_time, current_rate, proposed_leverage, max_leverage,
                                           entry_tag, side, **kwargs)
        self._now = current_time
        return super().leverage(pair, current_time, current_rate, proposed_leverage, max_leverage, entry_tag, side,
                                **kwargs)

    def confirm_trade_entry(self, pair, order_type, amount, rate, time_in_force, current_time, entry_tag, side,
                            **kwargs) -> bool:
        if MODE == "off":
            return True
        self._now = current_time
        allow = super().confirm_trade_entry(pair, order_type, amount, rate, time_in_force, current_time, entry_tag,
                                            side, **kwargs)
        return True if MODE == "record" else allow
