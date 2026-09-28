"""Install-time helpers for NovaeonTradingAI (stdlib only; run with the engine's Python).

  configure  write/refresh user_data/bot.json (API server: 127.0.0.1, port, generated secrets), user_data/novaeon.json
             (AI leverage opt-in, allowed by RAM/model; sentinel_build) and login.txt. Existing secrets and user choices are kept.
  plists     write the three launchd agents (<prefix>.engine / .control / .sentinel) with absolute paths.
  password   set a new random login password (bot.json + login.txt); restart the engine afterwards.
"""
import argparse
import json
import os
import plistlib
import secrets
import string
from pathlib import Path


def _write_json(path: Path, data, mode=0o600):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=4) + "\n")
    os.chmod(tmp, mode)
    tmp.replace(path)


def _write_login(home: Path, user: str, password: str, port: int):
    p = home / "login.txt"
    p.write_text(f"url: http://127.0.0.1:{port}\nuser: {user}\npassword: {password}\n")
    os.chmod(p, 0o600)


def configure(a):
    home = Path(a.home)
    ud = home / "user_data"
    bot_path = ud / "bot.json"
    if bot_path.exists():   # update: keep secrets and login, only re-assert where the API listens
        bot = json.loads(bot_path.read_text())
    else:
        bot = json.loads(Path(a.example).read_text())
        api = bot["api_server"]
        api.update(username="admin", password=a.password, jwt_secret_key=a.jwt, ws_token=a.ws_token)
    api = bot.setdefault("api_server", {})
    api.update(enabled=True, listen_ip_address="127.0.0.1", listen_port=a.engine_port, CORS_origins=[])
    _write_json(bot_path, bot)
    _write_login(home, api["username"], api["password"], a.engine_port)

    # AI leverage: opt-in (off by default); on 8 GB Macs (4-bit model) it is not allowed at all.
    allowed = a.ai_leverage_allowed == "true"
    nv_path = ud / "novaeon.json"
    nv = json.loads(nv_path.read_text()) if nv_path.exists() else {}
    sect = nv.setdefault("novaeon", {})
    sect.setdefault("ai_leverage", False)
    sect["ai_leverage_allowed"] = allowed
    sect["sentinel_build"] = a.sentinel_build   # shown by the control service (GET /control/settings)
    if not allowed:
        sect["ai_leverage"] = False
    _write_json(nv_path, nv, mode=0o644)
    # Practice money is the default: without user_data/mode.json run-bot.sh and control.py use "paper".


def _agent(label, args, home, log, env, keepalive=True, throttle=30, workdir=None):
    base_env = {"HOME": str(Path.home()), "PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "NOVAEON_HOME": str(home)}
    return {
        "Label": label,
        "ProgramArguments": args,
        "WorkingDirectory": str(workdir or home),
        "EnvironmentVariables": {**base_env, **env},
        "RunAtLoad": True,
        "KeepAlive": keepalive,
        "ThrottleInterval": throttle,
        "ProcessType": "Background",
        "StandardOutPath": str(log),
        "StandardErrorPath": str(log),
    }


def plists(a):
    home = Path(a.home)
    logs = home / "logs"
    logs.mkdir(exist_ok=True)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    p = a.prefix
    sentinel_url = f"http://127.0.0.1:{a.sentinel_port}/v1/systemone"
    engine_env = {"NOVAEON_LOG_FILE": str(logs / "engine.log"), "NOVAEON_SENTINEL_URL": sentinel_url}
    agents = {
        "engine": _agent(f"{p}.engine", ["/bin/bash", str(home / "bin/run-bot.sh")], home, logs / "engine.err",
                         engine_env, keepalive={"SuccessfulExit": False}, throttle=60),
        "control": _agent(f"{p}.control", [str(home / ".venv/bin/python"), str(home / "bin/control.py")], home,
                          logs / "control.log", {"NOVAEON_ENGINE_PORT": str(a.engine_port),
                                                 "NOVAEON_CONTROL_PORT": str(a.control_port),
                                                 "NOVAEON_ENGINE_LABEL": f"{p}.engine",
                                                 "NOVAEON_SENTINEL_URL": sentinel_url}),
        "sentinel": _agent(f"{p}.sentinel", [str(home / "sentinel/.venv/bin/python"), "-m", "sentinel.serve",
                                             "--run", str(a.model_dir), "--port", str(a.sentinel_port)],
                           home, logs / "sentinel.log",
                           {"PYTHONPATH": str(home / "sentinel"), "HF_HUB_OFFLINE": "1",
                            "HF_HOME": str(home / ".cache/huggingface"), "HF_HUB_DISABLE_TELEMETRY": "1"},
                           workdir=home / "sentinel"),
    }
    for name, d in agents.items():
        path = out / f"{d['Label']}.plist"
        path.write_bytes(plistlib.dumps(d))
        print(f"    wrote {path}")


def password(a):
    home = Path(a.home)
    bot_path = home / "user_data/bot.json"
    bot = json.loads(bot_path.read_text())
    alphabet = "".join(c for c in string.ascii_letters + string.digits if c not in "0O1lI")
    pw = "".join(secrets.choice(alphabet) for _ in range(20))
    bot["api_server"]["password"] = pw
    bot["api_server"]["jwt_secret_key"] = secrets.token_urlsafe(36)   # also signs out every open browser session
    _write_json(bot_path, bot)
    _write_login(home, bot["api_server"]["username"], pw, bot["api_server"]["listen_port"])
    print(pw)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("configure")
    c.add_argument("--home", required=True); c.add_argument("--example", required=True)
    c.add_argument("--engine-port", type=int, required=True)
    c.add_argument("--ai-leverage-allowed", choices=["true", "false"], required=True)
    c.add_argument("--sentinel-build", required=True)
    c.add_argument("--password", required=True); c.add_argument("--jwt", required=True); c.add_argument("--ws-token", required=True)
    pl = sub.add_parser("plists")
    pl.add_argument("--home", required=True); pl.add_argument("--prefix", required=True); pl.add_argument("--out", required=True)
    pl.add_argument("--engine-port", type=int, required=True); pl.add_argument("--control-port", type=int, required=True)
    pl.add_argument("--sentinel-port", type=int, required=True); pl.add_argument("--model-dir", required=True)
    pw = sub.add_parser("password")
    pw.add_argument("--home", required=True)
    a = ap.parse_args()
    {"configure": configure, "plists": plists, "password": password}[a.cmd](a)


if __name__ == "__main__":
    main()
