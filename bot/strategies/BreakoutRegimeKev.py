# BreakoutRegime + Novaeon Sentinel 9B (our news model, fine-tuned from the Kev-9B decision model by jaredpalmer):
# before each entry, Sentinel judges recent headlines about the coin. It blocks the trade on a major negative event
# and, only when AI leverage is switched on, picks leverage 1x-3x (1x without news). Fails open at 1x if Sentinel or
# the feeds are down. Every decision is appended to user_data/kev_decisions.jsonl for the A/B comparison.
# The class keeps its historical name BreakoutRegimeKev (stored in trades and configs); internal names (kev_*,
# custom-data key "kev") stay for compatibility with existing data.
#
# AI leverage policy (engine config, user_data/novaeon.json overlay loaded by bin/run-bot.sh):
#   "novaeon": {"ai_leverage": false,          # default: every new trade 1x. true: Sentinel picks 1x-3x
#               "ai_leverage_allowed": true}   # false (8 GB installs): 1x regardless of ai_leverage
# Dry/live runs on Macs with less than 12 GB of memory are always 1x (they run the smaller 4-bit Sentinel build).
# Manual stops from the UI (user_data/manual-stops.json, see bin/control.py) can raise a trade's stop; dry/live only.
import json
import logging
import os
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from math import isfinite
from pathlib import Path

from freqtrade.enums import RunMode
from freqtrade.strategy import stoploss_from_absolute

from BreakoutRegime import BreakoutRegime

log = logging.getLogger(__name__)

# Decision model: Novaeon Sentinel 9B (NOVAEON_SENTINEL_URL, or the older NOVAEON_KEV_URL). No fallback by default:
# the stock Kev-9B base model is much weaker on crypto news (bad-news precision 41% vs 78%, "clearly positive"
# precision 41% vs 83% on the held-out set), so if Sentinel is unreachable the bot trades without the news check at 1x
# instead. A fallback endpoint can still be set explicitly with NOVAEON_KEV_FALLBACK_URL. NOVAEON_SENTINEL_URL=off (installs
# without Sentinel) skips the call: every entry is allowed at 1x without the news check.
SENTINEL_URL = (os.environ.get("NOVAEON_SENTINEL_URL") or os.environ.get("NOVAEON_KEV_URL")
                or "http://127.0.0.1:8010/v1/systemone")
SENTINEL_OFF = SENTINEL_URL.strip().lower() in ("off", "none")
# Seconds to wait for one answer. 45 s is plenty for Apple GPUs and NVIDIA GPUs (well under a second); the experimental CPU
# mode sets more (a 9B model on a CPU without fast bf16 support takes minutes per news check).
SENTINEL_TIMEOUT = float(os.environ.get("NOVAEON_SENTINEL_TIMEOUT") or 45)
KEV_URLS = ([] if SENTINEL_OFF else [SENTINEL_URL]) + (
    [os.environ["NOVAEON_KEV_FALLBACK_URL"]] if os.environ.get("NOVAEON_KEV_FALLBACK_URL") else [])
FEEDS = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
    "https://decrypt.co/feed",
    "https://www.theblock.co/rss.xml",
]
# Coin names match case-insensitively; tickers only as uppercase words (so "ledger link" != LINK).
NAMES = {
    "BTC": ["bitcoin"], "ETH": ["ethereum", "ether"], "SOL": ["solana"], "BNB": ["bnb"],
    "XRP": ["xrp", "ripple"], "ADA": ["cardano"], "DOGE": ["dogecoin"], "AVAX": ["avalanche"],
    "LINK": ["chainlink"], "EGLD": ["multiversx", "elrond"],
    "NEAR": ["near protocol"], "ZEC": ["zcash"], "ONDO": ["ondo"], "ENA": ["ethena"], "LTC": ["litecoin"],
    "TAO": ["bittensor"], "SUI": ["sui"], "UNI": ["uniswap"], "ARB": ["arbitrum"], "WLD": ["worldcoin"],
    "AAVE": ["aave"],
}
VETO_THRESHOLD = 0.3
LEV2_POSITIVE = 0.5   # P(clearly positive news) for 2x
LEV3_POSITIVE = 0.75   # ... for 3x, and BTC daily close >= 5% above its EMA50
LEV3_BTC_STRENGTH = 1.05
MAX_LEVERAGE = 3.0
AI_LEVERAGE_MIN_RAM_GB = 12   # below this (8 GB Macs) AI leverage stays locked off in dry/live runs
HEADLINE_MAX_AGE_H = 48
LOG_PATH = Path(__file__).resolve().parents[1] / "kev_decisions.jsonl"
# Manual stops set in the UI (bin/control.py writes it): {"<trade_id>": {"price": <abs price>, "set_at": ts,
# "pair": ..., "open_timestamp": <ms>}}. pair/open_timestamp guard against trade ids reused by another database.
MANUAL_STOPS_PATH = Path(__file__).resolve().parents[1] / "manual-stops.json"


def _ram_gb() -> float:
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2**30
    except (ValueError, OSError, AttributeError):
        return float("inf")   # unknown: do not lock (the installer's ai_leverage_allowed flag still applies)


class BreakoutRegimeKev(BreakoutRegime):
    _feed_cache: tuple[float, list[dict]] = (0.0, [])
    _assess_cache: dict[str, tuple[float, dict]] = {}
    _pending_kev: dict[str, dict] = {}  # decision record waiting for the entry fill -> trade custom data
    _policy_logged = False
    # Manual stops only. Without a manual stop for a trade both callbacks below return None, which Freqtrade treats
    # as "no change", so the automatic strategy (and every backtest) behaves exactly as before.
    use_custom_stoploss = True
    _manual_stops: tuple[tuple | None, dict] = (None, {})

    def _manual_stop(self, trade) -> float | None:
        """Manual stop price for this open long trade, or None. Re-reads the file only when it changed."""
        if trade.is_short or self.config.get("runmode") not in (RunMode.DRY_RUN, RunMode.LIVE):
            return None
        try:
            st = MANUAL_STOPS_PATH.stat()
        except OSError:
            return None
        key = (st.st_mtime_ns, st.st_ino, st.st_size)
        if key != self._manual_stops[0]:
            try:
                data = json.loads(MANUAL_STOPS_PATH.read_text())
                if not isinstance(data, dict):
                    raise ValueError("not a JSON object")
            except (OSError, ValueError) as e:
                log.warning("manual-stops.json unreadable, ignoring manual stops: %s", e)
                data = {}
            BreakoutRegimeKev._manual_stops = (key, data)
        rec = self._manual_stops[1].get(str(trade.id))
        if not isinstance(rec, dict) or rec.get("pair", trade.pair) != trade.pair:
            return None
        ots = rec.get("open_timestamp")
        try:
            if ots is not None and abs(float(ots) - trade.open_date_utc.timestamp() * 1000) > 1000:
                return None
            price = float(rec["price"])
        except (KeyError, TypeError, ValueError):
            return None
        return price if isfinite(price) and price > 0 else None

    def custom_stoploss(self, pair, trade, current_time, current_rate, current_profit, **kwargs) -> float | None:
        """Raise the stop to the manual stop price. No `after_fill` parameter on purpose: Freqtrade then never calls
        this after order fills, the only path where it may lower a stop (allow_refresh). So stops only ever go up."""
        stop = self._manual_stop(trade)
        if stop is None or stop <= trade.stop_loss or current_rate <= stop:
            return None  # no manual stop / would not tighten / price already through it (custom_exit handles that)
        # A hair below the target so Freqtrade's ROUND_UP to the price tick lands exactly on it (not one tick above).
        return stoploss_from_absolute(stop * (1 - 1e-9), current_rate, is_short=False, leverage=trade.leverage or 1.0)

    def custom_exit(self, pair, trade, current_time, current_rate, current_profit, **kwargs):
        """Price fell through a manual stop before the stop could be raised to it (gap between two checks, or the
        engine was down): exit now, like a stop order would have."""
        stop = self._manual_stop(trade)
        if stop is not None and stop > trade.stop_loss and current_rate <= stop:
            return "manual_stop"
        return None

    def _headlines(self) -> list[dict]:
        ts, items = self._feed_cache
        if time.time() - ts < 900:
            return items
        items = []
        now = datetime.now(timezone.utc)
        for url in FEEDS:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                root = ET.fromstring(urllib.request.urlopen(req, timeout=10).read())
            except Exception as e:  # noqa: BLE001
                log.warning("feed failed %s: %s", url, e)
                continue
            for it in root.iter("item"):
                title = (it.findtext("title") or "").strip()
                desc = re.sub(r"<[^>]+>", "", it.findtext("description") or "").strip()[:200]
                try:
                    age_h = (now - parsedate_to_datetime(it.findtext("pubDate"))).total_seconds() / 3600
                except Exception:  # noqa: BLE001
                    age_h = 0
                if age_h <= HEADLINE_MAX_AGE_H:
                    items.append({"title": title, "summary": desc, "age_h": round(age_h, 1)})
        BreakoutRegimeKev._feed_cache = (time.time(), items)
        return items

    def _log(self, rec: dict) -> None:
        with LOG_PATH.open("a") as f:
            f.write(json.dumps(rec) + "\n")

    def _news_for(self, coin: str) -> list[dict]:
        words = NAMES.get(coin, [coin.lower()])
        by_name = re.compile(r"\b(" + "|".join(map(re.escape, words)) + r")\b", re.I)
        by_ticker = re.compile(r"\b" + re.escape(coin) + r"\b")
        return [h for h in self._headlines()
                if by_name.search(t := h["title"] + " " + h["summary"]) or by_ticker.search(t)][:15]

    def _ai_leverage_policy(self) -> tuple[bool, str | None]:
        """(on, reason_if_off). Off by default; see the header comment for the config flags."""
        nv = self.config.get("novaeon") or {}
        if not nv.get("ai_leverage_allowed", True):
            on, why = False, "ai_leverage_locked"
        elif (self.config.get("runmode") in (RunMode.DRY_RUN, RunMode.LIVE) and nv.get("sentinel_local", True)
              and _ram_gb() < AI_LEVERAGE_MIN_RAM_GB):   # small machine = 4-bit model; not when Sentinel runs elsewhere
            on, why = False, "ai_leverage_locked"
        elif not nv.get("ai_leverage", False):
            on, why = False, "ai_leverage_off"
        else:
            on, why = True, None
        if not BreakoutRegimeKev._policy_logged:
            BreakoutRegimeKev._policy_logged = True
            log.info("Sentinel leverage: %s", "on (Sentinel picks 1x-3x per new trade)" if on else
                     f"{'locked' if why == 'ai_leverage_locked' else 'off'} (every new trade uses 1x)")
        return on, why

    def bot_start(self, **kwargs) -> None:
        super().bot_start(**kwargs)
        self._ai_leverage_policy()   # log the policy once at startup

    def _assess(self, pair: str) -> dict:
        """One Sentinel call per entry (cached 120s): veto probability + news outlook. Shared by leverage() and
        confirm_trade_entry(), which Freqtrade calls in that order."""
        cached = self._assess_cache.get(pair)
        if cached and time.time() - cached[0] < 120:
            return cached[1]
        coin = pair.split("/")[0]
        news = self._news_for(coin)
        res = {"headlines": news, "p_negative": None, "outlook": None, "error": None}
        if news:
            body = {
                "model": "kev-latest",
                "state": {"coin": f"{coin} ({NAMES.get(coin, [coin])[0]})", "recent_headlines": news},
                "questions": {
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
                        "instructions": f"Overall, how do these headlines bear on {coin} specifically over the next "
                                        "few days?",
                        "criteria": {
                            "clearly_positive": f"Concrete, material good news for {coin} itself: major adoption or "
                                                "partnership, ETF or listing approval, strong inflows, upgrade shipped.",
                            "neutral_or_mixed": "Routine news, price commentary, mixed signals, or the coin is only "
                                                "mentioned in passing.",
                            "negative": f"Material bad news or risk for {coin}.",
                        },
                    },
                },
            }
            errors = []
            for url in KEV_URLS:
                try:
                    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                                 headers={"content-type": "application/json"})
                    ans = json.loads(urllib.request.urlopen(req, timeout=SENTINEL_TIMEOUT).read())["answers"]
                    res["p_negative"] = float(ans["major_negative"]["noul"])
                    res["outlook"] = {k: float(v) for k, v in ans["outlook"]["probabilities"].items()}
                    res["model"] = "novaeon-sentinel-9b" if url == SENTINEL_URL else "kev-9b"
                    break
                except Exception as e:  # noqa: BLE001
                    errors.append(f"{url.split('/')[2]}: {e}")
            else:
                res["error"] = "kev_unavailable: " + ("; ".join(errors) or "Sentinel is off on this install")
        self._assess_cache[pair] = (time.time(), res)
        return res

    def _btc_strength(self, pair: str) -> float | None:
        try:
            last = self.dp.get_analyzed_dataframe(pair, self.timeframe)[0].iloc[-1]
            return float(last["btc_close_1d"] / last["btc_ema50_1d"])
        except Exception:  # noqa: BLE001
            return None

    def leverage(self, pair, current_time, current_rate, proposed_leverage, max_leverage, entry_tag,
                 side, **kwargs) -> float:
        a = self._assess(pair)
        lev, why = 1.0, "no_news" if not a["headlines"] else "neutral"
        if a["error"]:
            why = "kev_unavailable"
        elif a["outlook"] and (a["p_negative"] or 0) < VETO_THRESHOLD:
            pos, btc = a["outlook"].get("clearly_positive", 0), self._btc_strength(pair)
            if pos >= LEV3_POSITIVE and btc and btc >= LEV3_BTC_STRENGTH:
                lev, why = 3.0, "clearly_positive+strong_btc"
            elif pos >= LEV2_POSITIVE:
                lev, why = 2.0, "clearly_positive"
        lev = min(lev, MAX_LEVERAGE, max_leverage)
        on, off_why = self._ai_leverage_policy()
        if not on:   # keep what Sentinel would have picked for the record, trade at 1x
            a["leverage_suggested"], lev, why = lev, min(1.0, max_leverage), off_why
        a["leverage"], a["leverage_reason"] = lev, why
        return lev

    def confirm_trade_entry(self, pair, order_type, amount, rate, time_in_force, current_time,
                            entry_tag, side, **kwargs) -> bool:
        a = self._assess(pair)
        rec = {"time": current_time.isoformat(), "pair": pair, "rate": rate, "headlines": len(a["headlines"]),
               "leverage": a.get("leverage", 1.0), "leverage_reason": a.get("leverage_reason"),
               "p_negative": a["p_negative"], "outlook": a["outlook"]}
        if "leverage_suggested" in a:
            rec["leverage_suggested"] = a["leverage_suggested"]
        self._assess_cache.pop(pair, None)
        if not a["headlines"]:
            self._log({**rec, "decision": "allow", "reason": "no_news"})
            self._pending_kev[pair] = {**rec, "decision": "allow", "reason": "no_news"}
            return True
        if a["error"]:
            self._log({**rec, "decision": "allow", "reason": a["error"]})
            self._pending_kev[pair] = {**rec, "decision": "allow", "reason": "kev_unavailable"}
            return True
        allow = a["p_negative"] < VETO_THRESHOLD
        titles = [h["title"] for h in a["headlines"][:8]]
        self._log({**rec, "decision": "allow" if allow else "veto", "titles": titles})
        if allow:
            self._pending_kev[pair] = {**rec, "decision": "allow", "titles": titles}
        if not allow:
            log.info("Sentinel veto %s: p_negative=%.2f", pair, a["p_negative"])
        return allow

    def order_filled(self, pair, trade, order, current_time, **kwargs) -> None:
        """Attach Sentinel's entry decision to the trade (read by NovaeonTradingAI via /trades/{id}/custom-data,
        key "kev" kept for existing trades)."""
        # First entry only: adding to a position (manual buy) skips the news check, so there is no new decision.
        if order.ft_order_side == trade.entry_side and trade.nr_of_successful_entries == 1 and pair in self._pending_kev:
            rec = self._pending_kev.pop(pair)
            if trade.leverage and rec.get("leverage") != trade.leverage:
                # A manual buy with a leverage picked by the user skips leverage(): record what the trade really uses.
                rec = {**rec, "leverage": trade.leverage, "leverage_reason": "manual"}
            trade.set_custom_data("kev", rec)
