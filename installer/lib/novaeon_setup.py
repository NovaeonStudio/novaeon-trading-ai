"""Install-time helpers for NovaeonTradingAI (stdlib only; run with the engine's or Sentinel's Python).

  configure  write/refresh user_data/bot.json (API server: 127.0.0.1, port, generated secrets), user_data/novaeon.json
             (AI leverage opt-in, allowed by RAM/model; sentinel_build/sentinel_mode) and login.txt. Existing secrets and
             user choices are kept.
  plists     macOS: write the launchd agents (<prefix>.engine / .control / .sentinel) with absolute paths.
  units      Linux: write the systemd user units (<prefix>-engine / -control / -sentinel .service) with absolute paths.
  password   set a new random login password (bot.json + login.txt); restart the engine afterwards.

plists/units write only the services named in --services (a Sentinel-only install has just "sentinel"; a bot that uses
a remote Sentinel or none has "engine,control").
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

    # AI leverage: opt-in (off by default); not allowed at all with the 4-bit model (8 GB Macs) or without Sentinel.
    allowed = a.ai_leverage_allowed == "true"
    nv_path = ud / "novaeon.json"
    nv = json.loads(nv_path.read_text()) if nv_path.exists() else {}
    sect = nv.setdefault("novaeon", {})
    sect.setdefault("ai_leverage", False)
    sect["ai_leverage_allowed"] = allowed
    sect["sentinel_build"] = a.sentinel_build   # shown by the control service (GET /control/settings)
    sect["sentinel_mode"] = a.sentinel_mode     # mlx | remote | cuda | cpu | off
    # Sentinel on another machine (split setup): this machine's memory says nothing about the model's precision, so the
    # strategy's "< 12 GB -> 4-bit model -> leverage locked" rule does not apply here.
    sect["sentinel_local"] = a.sentinel_mode in ("mlx", "cuda", "cpu")
    if not allowed:
        sect["ai_leverage"] = False
    _write_json(nv_path, nv, mode=0o644)
    # Practice money is the default: without user_data/mode.json run-bot.sh and control.py use "paper".


def _services(a):
    """name -> dict(args, env, log, workdir, restart_sec, description). Same content for launchd and systemd."""
    home = Path(a.home)
    logs = home / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    wanted = [s for s in a.services.split(",") if s]
    out = {}
    if "engine" in wanted:
        out["engine"] = dict(
            args=["/bin/bash", str(home / "bin/run-bot.sh")], log=logs / "engine.err", workdir=home, restart_sec=60,
            env={"NOVAEON_LOG_FILE": str(logs / "engine.log"), "NOVAEON_SENTINEL_URL": a.sentinel_url,
                 **({"NOVAEON_SENTINEL_TIMEOUT": str(a.sentinel_timeout)} if a.sentinel_timeout else {})},
            description="NovaeonTradingAI engine (trading bot)")
    if "control" in wanted:
        engine_ref = ({"NOVAEON_ENGINE_UNIT": f"{a.prefix}-engine.service"} if a.kind == "systemd"
                      else {"NOVAEON_ENGINE_LABEL": f"{a.prefix}.engine"})
        out["control"] = dict(
            args=[str(home / ".venv/bin/python"), str(home / "bin/control.py")], log=logs / "control.log", workdir=home,
            restart_sec=10, env={"NOVAEON_ENGINE_PORT": str(a.engine_port), "NOVAEON_CONTROL_PORT": str(a.control_port),
                                 **engine_ref, "NOVAEON_SENTINEL_URL": a.sentinel_url},
            description=f"NovaeonTradingAI control service (wallet, practice/real switch) on 127.0.0.1:{a.control_port}")
    if "sentinel" in wanted:
        env = {"PYTHONPATH": str(home / "sentinel"), "HF_HUB_OFFLINE": "1",
               "HF_HOME": a.hf_home or str(home / ".cache/huggingface"), "HF_HUB_DISABLE_TELEMETRY": "1"}
        if a.sentinel_device:   # cuda | cpu: Kev's torch backend (the MLX package path picks Metal by itself)
            env["SENTINEL_DEVICE"] = a.sentinel_device
        if a.sentinel_host != "127.0.0.1":
            env["SENTINEL_HOST"] = a.sentinel_host
        out["sentinel"] = dict(
            args=[str(home / "sentinel/.venv/bin/python"), "-m", "sentinel.serve", "--run", str(a.model_dir),
                  "--port", str(a.sentinel_port)],
            log=logs / "sentinel.log", workdir=home / "sentinel", restart_sec=30, env=env,
            description=f"Novaeon Sentinel model server on {a.sentinel_host}:{a.sentinel_port}")
    return out


def plists(a):
    a.kind = "launchd"
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    home = Path(a.home)
    for name, s in _services(a).items():
        label = f"{a.prefix}.{name}"
        d = {
            "Label": label,
            "ProgramArguments": s["args"],
            "WorkingDirectory": str(s["workdir"]),
            "EnvironmentVariables": {"HOME": str(Path.home()), "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
                                     "NOVAEON_HOME": str(home), **s["env"]},
            "RunAtLoad": True,
            # always restart, also the engine: a clean exit (e.g. SIGTERM after a hang) must not leave the bot off
            "KeepAlive": True,
            "ThrottleInterval": 60 if name == "engine" else 30,
            "ProcessType": "Background",
            "StandardOutPath": str(s["log"]),
            "StandardErrorPath": str(s["log"]),
        }
        path = out / f"{label}.plist"
        path.write_bytes(plistlib.dumps(d))
        print(f"    wrote {path}")


def _sd_quote(v: str) -> str:
    """One word for a systemd unit line: double-quoted, with the characters systemd would expand escaped."""
    v = str(v).replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%").replace("$", "$$")
    return f'"{v}"'


def _sd_path(v) -> str:
    """A path for WorkingDirectory=/EnvironmentFile=/append: (taken as is, no quotes; only specifiers are expanded)."""
    return str(v).replace("%", "%%")


def units(a):
    a.kind = "systemd"
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    home = Path(a.home)
    for name, s in _services(a).items():
        env = {"NOVAEON_HOME": str(home), "PATH": "/usr/local/bin:/usr/bin:/bin", **s["env"]}
        lines = ["# Written by the NovaeonTradingAI installer (installer/lib/novaeon_setup.py); rewritten on every update.",
                 "[Unit]", f"Description={s['description']}", "After=network-online.target",
                 "StartLimitIntervalSec=0", "", "[Service]", f"WorkingDirectory={_sd_path(s['workdir'])}"]
        lines += [f"Environment={_sd_quote(f'{k}={v}')}" for k, v in env.items()]
        if name == "sentinel":   # installer-managed settings, then the user's own (e.g. KEV_CUDA_GRAPHS=1, see docs/SENTINEL.md)
            lines.append(f"EnvironmentFile=-{_sd_path(home / 'sentinel/sentinel.env')}")
            lines.append(f"EnvironmentFile=-{_sd_path(home / 'sentinel/sentinel.local.env')}")
        lines += [f"ExecStart={' '.join(_sd_quote(x) for x in s['args'])}",
                  "Restart=always", f"RestartSec={s['restart_sec']}",
                  "SuccessExitStatus=130 143",   # the engine exits 130 on SIGTERM: a plain stop is not a failure
                  f"StandardOutput=append:{_sd_path(s['log'])}", f"StandardError=append:{_sd_path(s['log'])}",
                  "", "[Install]", "WantedBy=default.target", ""]
        path = out / f"{a.prefix}-{name}.service"
        tmp = path.with_suffix(".tmp")
        tmp.write_text("\n".join(lines))
        os.chmod(tmp, 0o644)
        tmp.replace(path)
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
    c.add_argument("--sentinel-mode", choices=["mlx", "remote", "cuda", "cpu", "off"], default="mlx")
    c.add_argument("--password", required=True); c.add_argument("--jwt", required=True); c.add_argument("--ws-token", required=True)
    for name in ("plists", "units"):
        pl = sub.add_parser(name)
        pl.add_argument("--home", required=True); pl.add_argument("--prefix", required=True); pl.add_argument("--out", required=True)
        pl.add_argument("--services", default="engine,control,sentinel")
        pl.add_argument("--engine-port", type=int, default=8081); pl.add_argument("--control-port", type=int, default=8082)
        pl.add_argument("--sentinel-port", type=int, default=8010); pl.add_argument("--model-dir", default="")
        pl.add_argument("--sentinel-url", default="", help="what engine/control ask; default: the local Sentinel port")
        pl.add_argument("--sentinel-device", choices=["", "cuda", "cpu"], default="")
        pl.add_argument("--sentinel-host", default="127.0.0.1")
        pl.add_argument("--hf-home", default="", help="Hugging Face cache of the base model (cuda/cpu)")
        pl.add_argument("--sentinel-timeout", type=int, default=0, help="seconds the engine waits for an answer (0 = 45)")
    pw = sub.add_parser("password")
    pw.add_argument("--home", required=True)
    a = ap.parse_args()
    if a.cmd in ("plists", "units") and not a.sentinel_url:
        a.sentinel_url = f"http://127.0.0.1:{a.sentinel_port}/v1/systemone"
    {"configure": configure, "plists": plists, "units": units, "password": password}[a.cmd](a)


if __name__ == "__main__":
    main()
