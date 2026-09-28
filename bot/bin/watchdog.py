#!/usr/bin/env python3
"""NovaeonTradingAI bot watchdog: prints one line per *change* of a problem state, nothing while healthy.

  ALERT <key>: <plain-language message>     when a problem starts
  RESOLVED <key>: <plain-language message>  when it is over

Read-only: it only looks (bot API, log, engine patch); it never changes anything.
Run long-lived (default) or once with --once. A supervisor process can relay the ALERT/RESOLVED lines (for example to a chat).
"""
import base64
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(os.environ.get("NOVAEON_HOME", Path(__file__).resolve().parents[1]))   # install folder
API = f"http://127.0.0.1:{os.environ.get('NOVAEON_ENGINE_PORT', '8081')}/api/v1"
LOG = Path(os.environ.get("NOVAEON_LOG_FILE", ROOT / "logs/engine.log"))
ENGINE_MODELS = ROOT / ".venv/lib/python3.12/site-packages/freqtrade/persistence/models.py"
_LOGIN = (ROOT / "login.txt").read_text()  # "user: <name>" and "password: <pw>" lines
USER = re.search(r"user: (\S+)", _LOGIN).group(1)
PW = re.search(r"password: (\S+)", _LOGIN).group(1)
AUTH = "Basic " + base64.b64encode(f"{USER}:{PW}".encode()).decode()
INTERVAL = 60
DRAWDOWN_ALERT = 0.15

active: dict[str, str] = {}
log_pos = LOG.stat().st_size if LOG.exists() else 0


def api(path: str):
    req = urllib.request.Request(f"{API}/{path}", headers={"Authorization": AUTH})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def new_log_lines() -> list[str]:
    global log_pos
    if not LOG.exists():
        return []
    size = LOG.stat().st_size
    if size < log_pos:  # rotated
        log_pos = 0
    with LOG.open("rb") as f:
        f.seek(log_pos)
        data = f.read()
    log_pos = size
    return data.decode(errors="replace").splitlines()


def check() -> dict[str, str]:
    problems: dict[str, str] = {}
    try:
        health = api("health")
        cfg = api("show_config")
        profit = api("profit")
        locks = api("locks").get("locks", [])
    except Exception as e:  # noqa: BLE001
        problems["offline"] = f"The trading bot is not answering ({e.__class__.__name__}). It may have crashed or be restarting."
        return problems
    age = time.time() - (health.get("last_process_ts") or 0)
    if age > 300:
        problems["stalled"] = f"The bot has not completed a cycle for {int(age // 60)} minutes."
    state = cfg.get("state")
    if state == "stopped":
        problems["stopped"] = "The bot is stopped and not trading."
    now_ms = time.time() * 1000
    brake = [lk for lk in locks if lk.get("pair") in ("*", "all") and lk.get("lock_end_timestamp", 0) > now_ms]
    if brake:
        until = time.strftime("%H:%M", time.localtime(brake[0]["lock_end_timestamp"] / 1000))
        problems["brake"] = f"Emergency brake is on until {until}: several safety stops in a short time. Buying is paused automatically."
    dd = profit.get("current_drawdown") or 0
    if dd >= DRAWDOWN_ALERT:
        problems["drawdown"] = f"The bot is {dd:.0%} below its highest point (alert level {DRAWDOWN_ALERT:.0%})."
    engine_src = ENGINE_MODELS.read_text()
    if "NovaeonTradingAI patch" not in engine_src and "NovaTradeUI patch" not in engine_src:
        problems["engine_patch"] = "The engine DB-pool patch is missing (Freqtrade was probably updated). Run bin/ensure-engine-patches.sh in the install folder, then bin/novaeon restart."
    lines = new_log_lines()
    bad = [ln for ln in lines if re.search(r"Fatal exception|QueuePool limit|Unable to exit trade", ln)]
    if len(bad) >= 3:
        problems["engine_errors"] = f"{len(bad)} serious engine errors in the last minute, e.g.: {bad[-1][20:180]}"
    return problems


def main() -> None:
    once = "--once" in sys.argv
    while True:
        now = check()
        for key, msg in now.items():
            if key not in active:
                print(f"ALERT {key}: {msg}", flush=True)
        for key, msg in list(active.items()):
            if key not in now:
                print(f"RESOLVED {key}: {msg.split(':')[0] if key == 'brake' else 'back to normal'}", flush=True)
        active.clear()
        active.update(now)
        if once:
            if not now:
                print("OK: no problems", flush=True)
            return
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
