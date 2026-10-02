"""NovaeonTradingAI control service: wallet connection (MetaMask -> Hyperliquid API wallet) and the paper/live switch.

Runs on 127.0.0.1:8082 (engine port + 1), reached by the UI directly or under /control behind your own proxy. Every request must carry the same
Bearer token the UI uses for the trading engine; it is checked against the engine's API (no separate login).

Security model:
- The user's MetaMask key never leaves MetaMask. MetaMask only signs Hyperliquid's "ApproveAgent" message, which lets
  a bot key (the "API wallet") place orders for the account. An API wallet cannot withdraw funds.
- The bot key is generated here and stored only in the macOS login Keychain (service novaeon-trading-agent), or on
  Linux as an encrypted systemd user credential bound to this user and machine.
- Live mode starts only after explicit confirmation, with an approved API wallet, a funded account and a capital cap.
- Manual trading: buys go through /control/buy (long only, tag "manual", add limit enforced) and manual stops through
  /control/trades/{id}/stop. Stops can only be tightened; the engine never lowers a stop.
- AI leverage (Sentinel picks 1-3x per new trade) is off unless the user switches it on (/control/settings); it stays
  locked off where user_data/novaeon.json says ai_leverage_allowed=false (8 GB installs) or the Mac has < 12 GB.
"""
import json
import math
import os
import secrets
import subprocess
import sys
import time
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import httpx
from ccxt.static_dependencies.keccak.keccak import SHA3
from coincurve import PrivateKey
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

ROOT = Path(os.environ.get("NOVAEON_HOME", Path(__file__).resolve().parents[1]))
UD = ROOT / "user_data"
MODE_FILE = UD / "mode.json"
LIVE_FILE = UD / "live.json"
WALLET_FILE = UD / "wallet.json"
PRACTICE_FILE = UD / "practice.json"   # {"dry_run_wallet": ...}: engine config overlay, loaded by run-bot.sh in paper mode
PRACTICE_LEDGER = UD / "practice-ledger.json"   # start amount, top-ups and which database the current practice run uses
AUDIT_FILE = UD / "control-audit.jsonl"
MANUAL_STOPS = UD / "manual-stops.json"   # {"<trade_id>": {...}}: read by the strategy (BreakoutRegimeKev) every loop
KEV_LOG = UD / "kev_decisions.jsonl"   # Sentinel's entry decisions (historical file name)
NOVAEON_FILE = UD / "novaeon.json"   # {"novaeon": {"ai_leverage", "ai_leverage_allowed", ...}}: engine config overlay
SENTINEL_URL = (os.environ.get("NOVAEON_SENTINEL_URL") or os.environ.get("NOVAEON_KEV_URL")
                or "http://127.0.0.1:8010/v1/systemone")
AI_LEVERAGE_MIN_RAM_GB = 12   # same threshold as the strategy (BreakoutRegimeKev.AI_LEVERAGE_MIN_RAM_GB)
ENGINE = f"http://127.0.0.1:{os.environ.get('NOVAEON_ENGINE_PORT', '8081')}/api/v1"
HL = "https://api.hyperliquid.xyz"
KC_SERVICE = "novaeon-trading-agent"
KC_PENDING = "novaeon-trading-agent-pending"
AGENT_NAME = "NovaeonTradingAI"
LAUNCHD_LABEL = os.environ.get("NOVAEON_ENGINE_LABEL", "studio.novaeon.trading.engine")
MIN_CAPITAL = 20.0  # Hyperliquid's minimum order is 10 USDC; below ~2 orders the bot can't trade sensibly
CONFIRM_PHRASE = "REAL MONEY"
MAX_MANUAL_LEVERAGE = 3.0   # same cap as the strategy's own leverage (BreakoutRegimeKev.MAX_LEVERAGE)
PRACTICE_MAX = 1_000_000.0   # keeps typos like 1e9 from producing absurd practice balances

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
# Local installs reach this service on its own port (no reverse proxy), so allow the UI's local origins.
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
_ui_port = os.environ.get("NOVAEON_ENGINE_PORT", "8081")
app.add_middleware(CORSMiddleware, allow_origins=[f"http://127.0.0.1:{_ui_port}", f"http://localhost:{_ui_port}"],
                   allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type"])
_auth_cache: dict[str, float] = {}


# ---------- helpers ----------
def _checksum(addr_hex: str) -> str:
    a = addr_hex.lower().removeprefix("0x")
    h = SHA3(a.encode()).hex()
    return "0x" + "".join(c.upper() if int(h[i], 16) >= 8 else c for i, c in enumerate(a))


def _new_key() -> tuple[str, str]:
    key = secrets.token_bytes(32)
    pub = PrivateKey(key).public_key.format(compressed=False)[1:]
    return "0x" + key.hex(), _checksum(SHA3(pub)[-20:].hex())


def _valid_addr(a: str) -> str:
    a = (a or "").strip()
    if len(a) != 42 or not a.startswith("0x") or any(c not in "0123456789abcdefABCDEF" for c in a[2:]):
        raise HTTPException(400, "Not a valid wallet address.")
    return _checksum(a)


# Key store for the bot's API-wallet key. macOS: login Keychain. Linux: a systemd user credential - encrypted with the
# host key (and TPM when present), bound to this user on this machine; nothing readable is ever written to disk.
_MAC = sys.platform == "darwin"
_CRED_DIR = Path.home() / ".config/novaeon/credentials"


def _cred(service: str, account: str) -> tuple[Path, str]:
    name = f"{service}.{account.lower()}"
    return _CRED_DIR / f"{name}.cred", name


def _kc_set(service: str, account: str, secret: str) -> None:
    if _MAC:
        subprocess.run(["security", "add-generic-password", "-U", "-s", service, "-a", account, "-w", secret],
                       check=True, capture_output=True)
        return
    _CRED_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(_CRED_DIR, 0o700)
    path, name = _cred(service, account)
    tmp = path.with_suffix(".tmp")
    r = subprocess.run(["systemd-creds", "--user", "encrypt", f"--name={name}", "-", str(tmp)],
                       input=secret.encode(), capture_output=True)
    if r.returncode != 0:
        tmp.unlink(missing_ok=True)
        raise HTTPException(500, "Could not store the bot key securely on this server.")
    os.chmod(tmp, 0o600)
    tmp.replace(path)


def _kc_get(service: str, account: str) -> str | None:
    if _MAC:
        r = subprocess.run(["security", "find-generic-password", "-s", service, "-a", account, "-w"],
                           capture_output=True, text=True)
        return r.stdout.strip() if r.returncode == 0 else None
    path, name = _cred(service, account)
    if not path.exists():
        return None
    r = subprocess.run(["systemd-creds", "--user", "decrypt", f"--name={name}", str(path), "-"],
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None


def _kc_del(service: str, account: str) -> None:
    if _MAC:
        subprocess.run(["security", "delete-generic-password", "-s", service, "-a", account], capture_output=True)
        return
    _cred(service, account)[0].unlink(missing_ok=True)


def _read(path: Path, default):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _write(path: Path, data) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1))
    os.chmod(tmp, 0o600)
    tmp.replace(path)


def _audit(event: str, **kw) -> None:
    with AUDIT_FILE.open("a") as f:
        f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "event": event, **kw}) + "\n")


def _hl_info(payload: dict):
    r = httpx.post(f"{HL}/info", json=payload, timeout=10)
    r.raise_for_status()
    return r.json()


def _agent_approved(wallet: str, agent: str) -> bool:
    try:
        agents = _hl_info({"type": "extraAgents", "user": wallet})
    except httpx.HTTPError:
        return False
    return any(a.get("address", "").lower() == agent.lower() for a in agents)


def _balance(wallet: str) -> dict:
    """USDC the bot can use: perp account value + spot USDC (unified accounts keep margin in spot)."""
    out = {"perp": 0.0, "spot_usdc": 0.0, "total": 0.0, "error": None}
    try:
        perp = _hl_info({"type": "clearinghouseState", "user": wallet})
        out["perp"] = float(perp.get("marginSummary", {}).get("accountValue", 0))
        spot = _hl_info({"type": "spotClearinghouseState", "user": wallet})
        out["spot_usdc"] = sum(float(b["total"]) for b in spot.get("balances", []) if b.get("coin") == "USDC")
        out["total"] = round(out["perp"] + out["spot_usdc"], 2)
    except (httpx.HTTPError, ValueError, KeyError) as e:
        out["error"] = f"Could not read the balance from Hyperliquid ({type(e).__name__})."
    return out


def _engine(path: str, auth: str):
    r = httpx.get(f"{ENGINE}/{path}", headers={"Authorization": auth}, timeout=10)
    r.raise_for_status()
    return r.json()


def _restart_engine() -> None:
    if sys.platform == "darwin":
        cmd = ["launchctl", "kickstart", "-k", f"gui/{os.getuid()}/{LAUNCHD_LABEL}"]
    else:  # Linux server: the engine runs as a systemd user service
        cmd = ["systemctl", "--user", "restart", os.environ.get("NOVAEON_ENGINE_UNIT", "novaeon-freqtrade.service")]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        raise HTTPException(502, "The change is saved, but the bot could not be restarted. Restart the app to apply it.")


def auth(authorization: str = Header(default="")) -> str:
    """Accept only callers holding a valid engine token (same login as the UI)."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Please log in.")
    if _auth_cache.get(authorization, 0) > time.time():
        return authorization
    try:
        r = httpx.get(f"{ENGINE}/show_config", headers={"Authorization": authorization}, timeout=10)
    except httpx.HTTPError:
        raise HTTPException(503, "The trading engine is not reachable.")
    if r.status_code != 200:
        raise HTTPException(401, "Please log in again.")
    _auth_cache[authorization] = time.time() + 60
    return authorization


# ---------- API ----------
@app.get("/control/status")
def status(a: str = Depends(auth)):
    mode = _read(MODE_FILE, {"mode": "paper"})
    w = _read(WALLET_FILE, {})
    wallet = w.get("walletAddress")
    agent = w.get("agentAddress")
    approved = bool(wallet and agent and _kc_get(KC_SERVICE, wallet) and _agent_approved(wallet, agent))
    bal = _balance(wallet) if wallet else None
    try:
        cfg = _engine("show_config", a)
        engine = {"online": True, "dry_run": cfg.get("dry_run"), "state": cfg.get("state")}
        engine["open_trades"] = _engine("count", a).get("current", 0)
    except httpx.HTTPError:
        engine = {"online": False, "dry_run": None, "state": None, "open_trades": None}
    live = _read(LIVE_FILE, {})
    return {
        "mode": mode.get("mode", "paper"),
        "since": mode.get("since"),
        "capital": live.get("available_capital"),
        "wallet": {"address": wallet, "agentAddress": agent, "approved": approved, "approvedAt": w.get("approvedAt"),
                   "balance": bal},
        "engine": engine,
        "confirmPhrase": CONFIRM_PHRASE,
        "minCapital": MIN_CAPITAL,
    }


@app.get("/control/balance/{address}")
def balance(address: str, a: str = Depends(auth)):
    """Balance of a connected (not yet approved) wallet, so the UI can guide the deposit step."""
    return _balance(_valid_addr(address))


class AgentStart(BaseModel):
    walletAddress: str


@app.post("/control/agent/start")
def agent_start(body: AgentStart, a: str = Depends(auth)):
    """Create a fresh bot key and return the ApproveAgent action for MetaMask to sign."""
    if _read(MODE_FILE, {}).get("mode") == "live":
        raise HTTPException(409, "Switch to practice mode before changing the wallet.")
    wallet = _valid_addr(body.walletAddress)
    key, agent = _new_key()
    _kc_set(KC_PENDING, agent, key)
    nonce = int(time.time() * 1000)
    # The UI adds signatureChainId (the wallet's current chain) and asks MetaMask to sign these fields (EIP-712,
    # domain HyperliquidSignTransaction v1, primaryType "HyperliquidTransaction:ApproveAgent").
    action = {"type": "approveAgent", "hyperliquidChain": "Mainnet", "agentAddress": agent, "agentName": AGENT_NAME,
              "nonce": nonce}
    _audit("agent_start", wallet=wallet, agent=agent)
    return {"walletAddress": wallet, "action": action}


class AgentConfirm(BaseModel):
    walletAddress: str
    action: dict
    signature: dict


@app.post("/control/agent/confirm")
def agent_confirm(body: AgentConfirm, a: str = Depends(auth)):
    wallet = _valid_addr(body.walletAddress)
    act = body.action
    agent = act.get("agentAddress", "")
    key = _kc_get(KC_PENDING, agent)
    if not key:
        raise HTTPException(400, "This approval request expired. Please start again.")
    if act.get("type") != "approveAgent" or act.get("agentName") != AGENT_NAME or act.get("hyperliquidChain") != "Mainnet":
        raise HTTPException(400, "Unexpected approval data.")
    sig = body.signature
    if not all(k in sig for k in ("r", "s", "v")):
        raise HTTPException(400, "Missing signature.")
    r = httpx.post(f"{HL}/exchange", json={"action": act, "nonce": act["nonce"], "signature": sig, "vaultAddress": None},
                   timeout=15)
    try:
        res = r.json()
    except ValueError:
        res = {"status": "err", "response": r.text[:300]}
    if r.status_code != 200 or res.get("status") != "ok":
        _audit("agent_reject", wallet=wallet, agent=agent, response=str(res)[:300])
        raise HTTPException(400, f"Hyperliquid refused the approval: {res.get('response', res)}")
    for _ in range(10):
        if _agent_approved(wallet, agent):
            break
        time.sleep(1)
    else:
        raise HTTPException(502, "Hyperliquid accepted the request, but the approval is not visible yet. "
                                 "Refresh in a minute. If it does not show up, the signing wallet may differ "
                                 "from the connected address, or the account may have no funds yet.")
    old = _read(WALLET_FILE, {}).get("walletAddress")
    if old and old != wallet:
        _kc_del(KC_SERVICE, old)
    _kc_set(KC_SERVICE, wallet, key)
    _kc_del(KC_PENDING, agent)
    _write(WALLET_FILE, {"walletAddress": wallet, "agentAddress": agent, "approvedAt": int(time.time())})
    _audit("agent_approved", wallet=wallet, agent=agent)
    return {"ok": True, "walletAddress": wallet, "agentAddress": agent}


@app.post("/control/wallet/forget")
def wallet_forget(a: str = Depends(auth)):
    if _read(MODE_FILE, {}).get("mode") == "live":
        raise HTTPException(409, "Switch to practice mode before disconnecting the wallet.")
    w = _read(WALLET_FILE, {})
    if w.get("walletAddress"):
        _kc_del(KC_SERVICE, w["walletAddress"])
    WALLET_FILE.unlink(missing_ok=True)
    _audit("wallet_forget", wallet=w.get("walletAddress"))
    return {"ok": True}


def _practice() -> dict:
    """Practice-money ledger. `dry_run_wallet` is what the engine starts from; `added` lists every top-up."""
    p = _read(PRACTICE_LEDGER, None)
    if p is None:
        base = _read(PRACTICE_FILE, {}).get("dry_run_wallet") or _read(UD / "config.json", {}).get("dry_run_wallet", 1000)
        p = {"dry_run_wallet": base, "started_with": base, "started_at": None, "added": [],
             "db": "paper-hyperliquid.sqlite"}
    return p


def _save_practice(p: dict) -> None:
    _write(PRACTICE_LEDGER, p)
    _write(PRACTICE_FILE, {"dry_run_wallet": p["dry_run_wallet"]})
    for f in (PRACTICE_LEDGER, PRACTICE_FILE):
        os.chmod(f, 0o644)   # not secret; run-bot.sh reads them


def _practice_amount(v: float) -> float:
    if not (1 <= v <= PRACTICE_MAX):
        raise HTTPException(400, f"Choose an amount between 1 and {PRACTICE_MAX:,.0f} USDC.")
    return round(v, 2)


def _require_paper() -> None:
    if _read(MODE_FILE, {}).get("mode") == "live":
        raise HTTPException(409, "Practice money only exists in practice mode. The bot is trading real money now.")


@app.get("/control/practice")
def practice(a: str = Depends(auth)):
    p = _practice()
    return {**p, "total_added": round(sum(x["amount"] for x in p["added"]), 2), "max": PRACTICE_MAX}


class PracticeAmount(BaseModel):
    amount: float


@app.post("/control/practice/add")
def practice_add(body: PracticeAmount, a: str = Depends(auth)):
    """Top up the practice balance. Open practice coins stay; the engine restarts (~20 s) to load the new balance."""
    _require_paper()
    amt = _practice_amount(body.amount)
    p = _practice()
    if p["dry_run_wallet"] + amt > PRACTICE_MAX:
        raise HTTPException(400, f"Practice money is capped at {PRACTICE_MAX:,.0f} USDC in total.")
    p["dry_run_wallet"] = round(p["dry_run_wallet"] + amt, 2)
    p["added"].append({"ts": int(time.time()), "amount": amt})
    _save_practice(p)
    _audit("practice_add", amount=amt, dry_run_wallet=p["dry_run_wallet"])
    _restart_engine()
    return {"ok": True, "dry_run_wallet": p["dry_run_wallet"]}


class PracticeReset(BaseModel):
    amount: float
    confirm: bool = False


@app.post("/control/practice/reset")
def practice_reset(body: PracticeReset, a: str = Depends(auth)):
    """Start practice over with a fresh database. The old practice history stays on disk untouched."""
    _require_paper()
    if not body.confirm:
        raise HTTPException(400, "Please confirm that practice should start over.")
    amt = _practice_amount(body.amount)
    old = _practice().get("db")
    db = f"paper-hyperliquid-{time.strftime('%Y%m%d-%H%M%S')}.sqlite"
    _save_practice({"dry_run_wallet": amt, "started_with": amt, "started_at": int(time.time()), "added": [],
                    "db": db, "previous_db": old})
    _audit("practice_reset", amount=amt, db=db, previous_db=old)
    _restart_engine()
    return {"ok": True, "dry_run_wallet": amt}


class ModeChange(BaseModel):
    mode: str
    capital: float | None = None
    confirm: str | None = None


@app.post("/control/mode")
def set_mode(body: ModeChange, a: str = Depends(auth)):
    current = _read(MODE_FILE, {"mode": "paper"}).get("mode", "paper")
    if body.mode not in ("paper", "live"):
        raise HTTPException(400, "Unknown mode.")
    if body.mode == current:
        return {"ok": True, "mode": current, "unchanged": True}
    try:
        open_trades = _engine("count", a).get("current", 0)
    except httpx.HTTPError:
        raise HTTPException(503, "The trading engine is not reachable, so the switch is not safe right now.")

    if body.mode == "paper":
        if open_trades:
            raise HTTPException(409, f"The bot still holds {open_trades} coin(s) with real money. Sell them first "
                                     "(My coins → Sell now), then switch back to practice.")
        _write(MODE_FILE, {"mode": "paper", "since": int(time.time())})
        _audit("mode_paper")
        _restart_engine()
        return {"ok": True, "mode": "paper"}

    # -> live
    if (body.confirm or "").strip().upper() != CONFIRM_PHRASE:
        raise HTTPException(400, f'Type "{CONFIRM_PHRASE}" to confirm.')
    w = _read(WALLET_FILE, {})
    wallet, agent = w.get("walletAddress"), w.get("agentAddress")
    if not (wallet and agent and _kc_get(KC_SERVICE, wallet)):
        raise HTTPException(409, "Connect your wallet and allow the bot to trade first.")
    if not _agent_approved(wallet, agent):
        raise HTTPException(409, "Hyperliquid no longer lists the bot's trading permission. Connect the wallet again.")
    bal = _balance(wallet)
    if bal["error"]:
        raise HTTPException(503, bal["error"])
    cap = float(body.capital or 0)
    if cap < MIN_CAPITAL:
        raise HTTPException(400, f"Use at least {MIN_CAPITAL:.0f} USDC.")
    if cap > bal["total"]:
        raise HTTPException(400, f"Your Hyperliquid account only has {bal['total']:.2f} USDC.")
    _write(LIVE_FILE, {
        "dry_run": False,
        "available_capital": round(cap, 2),
        "exchange": {"walletAddress": wallet},
        # Stops live on the exchange too, so coins stay protected even if this computer is off.
        "order_types": {"entry": "limit", "exit": "limit", "stoploss": "limit", "stoploss_on_exchange": True},
    })
    _write(MODE_FILE, {"mode": "live", "since": int(time.time())})
    _audit("mode_live", wallet=wallet, capital=cap, balance=bal["total"], paper_open_trades=open_trades)
    _restart_engine()
    return {"ok": True, "mode": "live", "capital": cap}


# ---------- settings: AI leverage ----------
_ram_cache: list[float | None] = []
_build_cache: dict = {"at": 0.0, "value": None}


def _ram_gb() -> float | None:
    if not _ram_cache:
        try:
            if _MAC:
                r = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=5)
                _ram_cache.append(round(int(r.stdout.strip()) / 2**30, 1))
            else:
                _ram_cache.append(round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2**30, 1))
        except (OSError, ValueError, AttributeError, subprocess.SubprocessError):
            _ram_cache.append(None)
    return _ram_cache[0]


def _novaeon() -> dict:
    d = _read(NOVAEON_FILE, {})
    return d if isinstance(d, dict) else {}


def _sentinel_build(nv: dict) -> str | None:
    """Which Sentinel build answers the news checks: the installer's note in novaeon.json, else asked from the model
    server (cached 5 min)."""
    if nv.get("sentinel_build"):
        return str(nv["sentinel_build"])
    if SENTINEL_URL.strip().lower() in ("off", "none"):
        return "off"
    if time.time() - _build_cache["at"] > 300:
        value = None
        try:
            base = SENTINEL_URL.split("/v1/")[0]
            m = httpx.get(f"{base}/v1/models", timeout=2).json()["models"][0]
            value = " ".join(str(x) for x in (m.get("backend"), m.get("dtype")) if x) or None
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
            pass
        _build_cache.update(at=time.time(), value=value)
    return _build_cache["value"]


def _settings() -> dict:
    nv = _novaeon().get("novaeon") or {}
    ram = _ram_gb()
    locked_reason = None
    machine = "This Mac" if _MAC else "This computer"
    if nv.get("sentinel_mode") == "off" or SENTINEL_URL.strip().lower() in ("off", "none"):
        locked_reason = ("Sentinel is switched off on this install, so there is no news check to pick leverage. "
                         "Every trade uses 1× (no borrowing).")
    elif not nv.get("ai_leverage_allowed", True):
        locked_reason = (f"{machine} runs the smaller Sentinel build, which is less precise at picking leverage. "
                         "Every trade uses 1× (no borrowing).")
    elif nv.get("sentinel_local", True) and ram is not None and ram < AI_LEVERAGE_MIN_RAM_GB:
        locked_reason = (f"{machine} has {ram:g} GB of memory and runs the smaller Sentinel build, which is less "
                         "precise at picking leverage. Every trade uses 1× (no borrowing).")
    allowed = locked_reason is None
    return {"ai_leverage": bool(nv.get("ai_leverage", False)) and allowed, "ai_leverage_allowed": allowed,
            "locked_reason": locked_reason, "ram_gb": ram, "sentinel_build": _sentinel_build(nv),
            "max_ai_leverage": 3, "mode": _read(MODE_FILE, {}).get("mode", "paper")}


@app.get("/control/settings")
def settings(a: str = Depends(auth)):
    """Bot-wide settings shown in the app: whether Sentinel may choose leverage (1-3x) for new trades."""
    return _settings()


class SettingsChange(BaseModel):
    ai_leverage: bool


@app.post("/control/settings")
def set_settings(body: SettingsChange, a: str = Depends(auth)):
    """Switch AI leverage on or off. Only new trades are affected: open positions keep their leverage. Allowed in
    both modes and with open trades; the engine restarts (~20 s) to load the change."""
    cur = _settings()
    if body.ai_leverage and not cur["ai_leverage_allowed"]:
        raise HTTPException(400, f"AI leverage is locked. {cur['locked_reason']}")
    if body.ai_leverage == cur["ai_leverage"]:
        return {**cur, "ok": True, "unchanged": True, "restarting": False}
    try:
        open_trades = _engine("count", a).get("current", 0)
    except httpx.HTTPError:
        open_trades = None
    d = _novaeon()
    d["novaeon"] = {**(d.get("novaeon") or {}), "ai_leverage": body.ai_leverage}
    d["novaeon"].setdefault("ai_leverage_allowed", True)
    _write(NOVAEON_FILE, d)
    os.chmod(NOVAEON_FILE, 0o644)   # not secret; run-bot.sh loads it
    _audit("ai_leverage_on" if body.ai_leverage else "ai_leverage_off", mode=cur["mode"], open_trades=open_trades)
    _restart_engine()
    note = ("Sentinel may now use up to 3× leverage on new trades." if body.ai_leverage
            else "New trades use 1× (no borrowing).")
    if open_trades:
        note += " Coins the bot already holds keep their current leverage."
    return {**_settings(), "ok": True, "unchanged": False, "restarting": True, "open_trades": open_trades,
            "note": note}


# ---------- manual trading: buys and stops ----------
# Verified in the Freqtrade 2026.8 source (2026-09-28):
# - /forceenter for a NEW coin runs the strategy's leverage() and confirm_trade_entry() (Sentinel news check, may veto);
#   adding to an OPEN position skips both (leverage stays the trade's, no news check) and Freqtrade does not enforce
#   max_entry_position_adjustment or can_short for forced entries, so this service does.
# - A long stop only ever moves up (Trade.adjust_stop_loss), so a manual stop can only tighten the current stop.
def _engine_post(path: str, auth: str, body: dict, timeout: float = 10):
    return httpx.post(f"{ENGINE}/{path}", headers={"Authorization": auth}, json=body, timeout=timeout)


def _open_trades(a: str) -> dict[int, dict]:
    try:
        return {t["trade_id"]: t for t in _engine("status", a)}
    except httpx.HTTPError:
        raise HTTPException(503, "The trading engine is not reachable.")


def _tick(t: dict) -> float | None:
    """Price tick of the trade's market (Hyperliquid reports tick sizes: precision mode 4 = TICK_SIZE)."""
    return t.get("price_precision") if t.get("precision_mode") == 4 else None


def _round_tick(t: dict, price: float) -> float:
    tick = _tick(t)
    return float(round(price / tick) * Decimal(str(tick))) if tick else price


def _manual_stops(trades: dict[int, dict]) -> dict:
    """Current manual stops; entries for trades that are no longer open are dropped (trade ids restart per database)."""
    stops = _read(MANUAL_STOPS, {})
    stops = stops if isinstance(stops, dict) else {}
    keep = {k: v for k, v in stops.items()
            if k.isdigit() and isinstance(v, dict) and int(k) in trades
            and v.get("pair") == trades[int(k)]["pair"] and v.get("open_timestamp") == trades[int(k)]["open_timestamp"]}
    if keep != stops:
        _write(MANUAL_STOPS, keep)
    return keep


def _levels(t: dict, manual: dict | None) -> dict:
    """Price levels of an open long trade. break_even covers the entry fee, the exit fee and funding paid so far."""
    amount, fee_open, fee_close = t["amount"], t.get("fee_open") or 0.0, t.get("fee_close") or 0.0
    tick = _tick(t)
    be = (t["open_trade_value"] - (t.get("funding_fees") or 0.0)) / (amount * (1 - fee_close)) if amount else None
    stop = t.get("stop_loss_abs")
    return {
        "trade_id": t["trade_id"], "pair": t["pair"], "leverage": t.get("leverage"), "open_rate": t["open_rate"],
        "current_rate": t.get("current_rate"), "price_tick": tick,
        "break_even": round(be, 8) if be else None,
        "break_even_fees_only": round(t["open_rate"] * (1 + fee_open) / (1 - fee_close), 8),
        "liquidation": t.get("liquidation_price"),
        "stop_loss_abs": stop, "initial_stop_loss_abs": t.get("initial_stop_loss_abs"),
        "stop_raised": bool(stop and t.get("initial_stop_loss_abs") and stop > t["initial_stop_loss_abs"]),
        "manual_stop": manual["price"] if manual else None,
        "manual_stop_set_at": manual.get("set_at") if manual else None,
        "manual_stop_active": bool(manual and stop is not None and stop >= manual["price"] - (tick or 0) / 2),
        "entries": t.get("nr_of_successful_entries"), "enter_tag": t.get("enter_tag"),
    }


@app.get("/control/stops")
def stops(a: str = Depends(auth)):
    """Manual stops of open trades only: {"<trade_id>": {price, set_at, pair, open_timestamp, stop_loss_abs, active}}."""
    trades = _open_trades(a)
    out = {}
    for k, v in _manual_stops(trades).items():
        lv = _levels(trades[int(k)], v)
        out[k] = {**v, "stop_loss_abs": lv["stop_loss_abs"], "active": lv["manual_stop_active"]}
    return out


@app.get("/control/levels")
def levels(a: str = Depends(auth)):
    """Every open trade: stop, manual stop (or null), break-even, liquidation price."""
    trades = _open_trades(a)
    ms = _manual_stops(trades)
    return {str(tid): _levels(t, ms.get(str(tid))) for tid, t in trades.items()}


def _tf_minutes(tf: str) -> int:
    """Minutes per candle for a Freqtrade timeframe string ("15m", "1h", "4h", "1d")."""
    unit = {"m": 1, "h": 60, "d": 1440, "w": 10080}[tf[-1]]
    return int(tf[:-1]) * unit


@app.get("/control/trades/{trade_id}/levels")
def trade_levels(trade_id: int, a: str = Depends(auth)):
    """_levels plus the strategy's own exit/entry lines from the engine's analyzed candles."""
    trades = _open_trades(a)
    t = trades.get(trade_id)
    if not t:
        raise HTTPException(404, "This trade is not open (any more).")
    out = _levels(t, _manual_stops(trades).get(str(trade_id)))
    out.update(exit_level=None, entry_level=None, candle=None, btc_regime_ok=None)
    try:
        tf = _engine("show_config", a).get("timeframe", "1h")
        # The strategy's windows are in hours (10-hour low, 20-hour high): convert to candles of this timeframe.
        cph = max(1, 60 // _tf_minutes(tf))
        n_exit, n_entry = 10 * cph, 20 * cph
        tf_ms = _tf_minutes(tf) * 60_000
        held = max(0, int((time.time() * 1000 - (t.get("open_timestamp") or 0)) // tf_ms)) + 2
        r = httpx.get(f"{ENGINE}/pair_candles",
                      params={"pair": t["pair"], "timeframe": tf, "limit": min(n_entry + 10 + held, 5000)},
                      headers={"Authorization": a}, timeout=10)
        r.raise_for_status()
        c = r.json()
        rows = [dict(zip(c["columns"], row)) for row in c["data"]]  # closed candles only (Freqtrade drops the open one)
        if len(rows) >= n_entry:
            last = rows[-1]
            # The next candle exits if it CLOSES below the exit level: the lowest low of the last 10 hours, but never
            # lower than the highest such level since the entry (ratchet exit, strategy v6).
            nxt = min(x["low"] for x in rows[-n_exit:])
            since = t.get("open_timestamp") or 0
            seen = [x["lo10"] for x in rows
                    if x.get("lo10") is not None and (x.get("__date_ts") or 0) >= since - tf_ms]
            out["exit_level"] = max([nxt, *seen])
            out["entry_level"] = max(x["high"] for x in rows[-n_entry:])
            out["candle"] = {"timeframe": tf, "last_closed": last["date"], "lo10": last.get("lo10"), "hi20": last.get("hi20")}
            if last.get("btc_close_1d") is not None and last.get("btc_ema50_1d") is not None:
                out["btc_regime_ok"] = last["btc_close_1d"] >= last["btc_ema50_1d"]
    except (httpx.HTTPError, KeyError, ValueError, TypeError):
        out["levels_error"] = "The strategy's chart levels are not available right now."
    return out


class StopChange(BaseModel):
    price: float | None = None


@app.post("/control/trades/{trade_id}/stop")
def set_stop(trade_id: int, body: StopChange, a: str = Depends(auth)):
    """Set (price) or remove (null) a manual stop. The strategy re-reads manual-stops.json every bot loop (~5 s)."""
    trades = _open_trades(a)
    t = trades.get(trade_id)
    if not t:
        raise HTTPException(404, "This trade is not open (any more).")
    if t.get("is_short"):
        raise HTTPException(400, "Manual stops are only supported for long positions.")
    stops_ = _manual_stops(trades)
    key, cur_stop, rate, pair = str(trade_id), t.get("stop_loss_abs"), t.get("current_rate"), t["pair"]
    live = _read(MODE_FILE, {}).get("mode") == "live"

    if body.price is None:
        old = stops_.pop(key, None)
        _write(MANUAL_STOPS, stops_)
        _audit("manual_stop_removed", trade_id=trade_id, pair=pair, price=old and old.get("price"), stop_loss_abs=cur_stop)
        return {"ok": True, "trade_id": trade_id, "pair": pair, "manual_stop": None, "manual_stop_set_at": None,
                "removed": old is not None,
                "stop_loss_abs": cur_stop,
                "note": "The manual stop is removed. A stop that was already raised stays where it is: the engine "
                        "never lowers a stop. It still sells if the price falls to it."}

    price = body.price
    if not math.isfinite(price) or price <= 0:
        raise HTTPException(400, "Enter a stop price above 0.")
    if rate is None or cur_stop is None:
        raise HTTPException(503, "The current price of this coin is not known yet. Try again in a few seconds.")
    price = _round_tick(t, price)
    prev = stops_.get(key)
    if prev and prev.get("price") == price and cur_stop >= price - (_tick(t) or 0) / 2:
        return {"ok": True, "trade_id": trade_id, "pair": pair, "manual_stop": price,
                "manual_stop_set_at": prev.get("set_at"), "applied": True,
                "unchanged": True, "stop_loss_abs": cur_stop}
    if price >= rate:
        raise HTTPException(400, f"A stop must be below the current price ({rate:g}). To sell now, use Close instead.")
    if price <= cur_stop:
        raise HTTPException(400, f"The stop can only be moved up. The current stop is {cur_stop:g}; a stop at or below "
                                 "it would have no effect, because the engine never lowers a stop.")
    liq = t.get("liquidation_price")
    if liq and price <= liq:
        raise HTTPException(400, f"A stop must be above the liquidation price ({liq:g}).")
    rec = {"price": price, "set_at": int(time.time()), "pair": pair, "open_timestamp": t["open_timestamp"]}
    stops_[key] = rec
    _write(MANUAL_STOPS, stops_)
    _audit("manual_stop_set", trade_id=trade_id, pair=pair, price=price, previous_manual=prev and prev.get("price"),
           stop_loss_abs=cur_stop, current_rate=rate, live=live)

    # Wait for the bot's next loop to move the stop, so the answer is definitive.
    applied, new_stop, closed = False, cur_stop, False
    deadline = time.time() + 20
    while time.time() < deadline:
        time.sleep(1.5)
        try:
            tt = _open_trades(a).get(trade_id)
        except HTTPException:
            continue
        if not tt:
            closed = True
            break
        new_stop = tt.get("stop_loss_abs")
        if new_stop is not None and new_stop >= price - (_tick(t) or 0) / 2:
            applied = True
            break
    note = ("The stop is raised." if applied else
            "The trade was closed in the meantime." if closed else
            "Saved. The bot applies it on its next check (it may be busy for a moment).")
    if applied and live:
        note += " The stop order on Hyperliquid follows within about a minute."
    return {"ok": True, "trade_id": trade_id, "pair": pair, "manual_stop": price, "manual_stop_set_at": rec["set_at"],
            "applied": applied, "closed": closed,
            "stop_loss_abs_before": cur_stop, "stop_loss_abs": new_stop, "distance_pct": round((1 - price / rate) * 100, 2),
            "note": note}


class ManualBuy(BaseModel):
    pair: str
    stake_amount: float | None = None   # USDC of own money; None = one regular slot, like the bot's own entries
    leverage: float | None = None       # new positions only, 1-3; None = Sentinel picks if AI leverage is on, else 1x
    ordertype: str | None = None        # "limit" (default, like the bot) or "market"


def _kev_veto(pair: str, since: float) -> dict | None:
    try:
        lines = KEV_LOG.read_text().splitlines()[-50:]
    except OSError:
        return None
    for line in reversed(lines):
        try:
            rec = json.loads(line)
            ts = datetime.fromisoformat(rec["time"]).timestamp()
        except (ValueError, KeyError):
            continue
        if rec.get("pair") == pair and ts >= since - 5:
            return rec if rec.get("decision") == "veto" else None
    return None


@app.post("/control/buy")
def manual_buy(body: ManualBuy, a: str = Depends(auth)):
    """Manual buy through the engine's /forceenter: long only, tagged "manual". A new coin gets Sentinel's news check
    (may veto) and, with AI leverage on, Sentinel's leverage (1-3x; otherwise 1x) unless `leverage` is given; adding to an open position keeps its leverage
    and skips the news check. Max 1 + max_entry_position_adjustment buys per position."""
    pair = (body.pair or "").strip()
    try:
        cfg = _engine("show_config", a)
        whitelist = _engine("whitelist", a).get("whitelist", [])
    except httpx.HTTPError:
        raise HTTPException(503, "The trading engine is not reachable.")
    if not cfg.get("force_entry_enable"):
        raise HTTPException(409, "Manual buys are switched off in the bot's settings.")
    if cfg.get("state") != "running":
        raise HTTPException(409, "The bot is not running.")
    if pair not in whitelist:
        raise HTTPException(400, "This coin is not on the bot's list.")
    stake = body.stake_amount
    if stake is not None and (not math.isfinite(stake) or stake <= 0):
        raise HTTPException(400, "Enter an amount above 0.")
    lev = body.leverage
    if lev is not None and (not math.isfinite(lev) or not 1 <= lev <= MAX_MANUAL_LEVERAGE):
        raise HTTPException(400, f"Choose a leverage between 1 and {MAX_MANUAL_LEVERAGE:g}.")
    if body.ordertype not in (None, "limit", "market"):
        raise HTTPException(400, "Order type must be limit or market.")
    open_t = next((t for t in _open_trades(a).values() if t["pair"] == pair), None)
    if open_t and lev is not None and lev != open_t.get("leverage"):
        raise HTTPException(400, f"An open position keeps its leverage ({open_t.get('leverage'):g}x).")
    if open_t:
        max_adj = cfg.get("max_entry_position_adjustment", -1)
        if not cfg.get("position_adjustment_enable"):
            raise HTTPException(409, "Adding to an open position is switched off in the bot's settings.")
        if open_t.get("has_open_orders"):
            raise HTTPException(409, "An order for this coin is still open. Wait until it fills or is cancelled.")
        if max_adj is not None and max_adj >= 0 and open_t["nr_of_successful_entries"] > max_adj:
            raise HTTPException(409, f"This position was already bought {open_t['nr_of_successful_entries']} times; "
                                     f"the limit is {max_adj + 1} buys per position.")
    payload = {"pair": pair, "side": "long", "entry_tag": "manual"}   # never short
    if stake is not None:
        payload["stakeamount"] = round(stake, 2)
    if lev is not None and not open_t:
        payload["leverage"] = lev   # replaces the AI's leverage choice; the news check (veto) still runs
    if body.ordertype:
        payload["ordertype"] = body.ordertype
    t0 = time.time()
    try:
        r = _engine_post("forceenter", a, payload, timeout=240)   # a new coin waits for the news check (up to ~2 min)
    except httpx.HTTPError:
        _audit("manual_buy_error", pair=pair, stake=stake, add=bool(open_t))
        raise HTTPException(504, "No answer from the trading engine. Check My coins before trying again.")
    try:
        res = r.json()
    except ValueError:
        res = {}
    if r.status_code != 200 or "trade_id" not in res:
        err = str(res.get("error") or res.get("status") or res.get("detail") or r.text[:200])
        veto = None if open_t else _kev_veto(pair, t0)
        _audit("manual_buy_failed", pair=pair, stake=stake, add=bool(open_t), error=err[:300], kev_veto=bool(veto))
        if veto:
            titles = "; ".join((veto.get("titles") or [])[:3])
            raise HTTPException(409, f"Sentinel, the AI news check, blocked this buy (risk {veto.get('p_negative', 0):.0%}). "
                                     f"Headlines: {titles}")
        raise HTTPException(400, f"The engine did not buy: {err.split(': ', 1)[-1]}")
    _audit("manual_buy", pair=pair, trade_id=res["trade_id"], stake=stake, add=bool(open_t),
           leverage=res.get("leverage"), entries=res.get("nr_of_successful_entries"))
    return {"ok": True, "trade_id": res["trade_id"], "pair": pair, "added_to_existing": bool(open_t),
            "news_checked": not open_t, "leverage": res.get("leverage"), "stake_amount": res.get("stake_amount"),
            "order_open": res.get("has_open_orders"), "entries": res.get("nr_of_successful_entries"),
            "enter_tag": res.get("enter_tag")}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("NOVAEON_CONTROL_PORT", "8082")), log_level="warning")
