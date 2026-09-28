#!/bin/bash
# NovaeonTradingAI installer for Apple Silicon Macs (macOS 14+).
#
#   curl -fsSL https://raw.githubusercontent.com/NovaeonStudio/novaeon-trading-ai/main/install.sh | bash
#
# Installs everything into ~/NovaeonTradingAI (or $NOVAEON_HOME): its own uv + Python, the trading engine, the web app,
# the Novaeon Sentinel model and three background services (launchd agents). No Homebrew, no Xcode tools, no sudo.
# Running it again updates an existing install and keeps your settings, trades and login.
#
# Defaults: practice money (no real funds), a random login password, the app only reachable from this Mac
# (127.0.0.1), leverage 1x. Nothing is sent anywhere unless you opt in to the anonymous install count.
#
# Environment overrides (all optional):
#   NOVAEON_HOME            install directory                       (default ~/NovaeonTradingAI)
#   NOVAEON_ENGINE_PORT     web app + engine API port               (default 8081)
#   NOVAEON_CONTROL_PORT    wallet/practice-money service port      (default: engine port + 1; the web app expects that)
#   NOVAEON_SENTINEL_PORT   Sentinel model server port              (default 8010)
#   NOVAEON_LABEL_PREFIX    launchd label prefix                    (default studio.novaeon.trading)
#   NOVAEON_REF             git branch or tag to install            (default main)
#   NOVAEON_MODEL_VARIANT   mlx-8bit | mlx-4bit                     (default: by RAM, >=16 GB -> 8-bit)
#   NOVAEON_MODEL_PATH      use an existing local Sentinel package instead of downloading it
#   NOVAEON_SRC_URL / NOVAEON_UI_URL / NOVAEON_UI_DIST   alternative source / web-app locations (testing, mirrors)
#   NOVAEON_TELEMETRY       yes | no: answer the install-count question without asking
#   NOVAEON_NO_OPEN=1       don't open the browser or copy the password at the end
#   NOVAEON_START=0         install/update only, don't (re)start the services (start later: bin/novaeon start)
#   NOVAEON_YES=1           non-interactive: accept defaults for every question
set -euo pipefail

# ---------------------------------------------------------------- constants (release engineering edits these)
GITHUB_REPO="NovaeonStudio/novaeon-trading-ai"
DEFAULT_REF="main"
HF_REPO="NovaeonStudio/novaeon-sentinel-9b"   # Hugging Face model repo (Sentinel MLX packages)
HF_REVISION="main"
HF_SUBFOLDER_8BIT="mlx-8bit"                   # >= 16 GB RAM
HF_SUBFOLDER_4BIT="mlx-4bit"                   # 8 GB RAM (AI leverage locked off)
SENTINEL_8BIT_SHA256="373bc466f1b795a080490dff3d4b952293909d930b9d053a09c8038250b1ea8a"   # pin of <subfolder>/model.safetensors (release 1.0.0)
SENTINEL_4BIT_SHA256="9dbad3f4805cfd62eb3a0319f06ab15d8dd87206a6ef961f6be7d7358706837a"
TELEMETRY_URL=""   # opt-in install count endpoint (planned: https://novaeon.studio/api/install-count); empty = never asked, nothing sent
UV_VERSION="0.12.17"
ENGINE_PYTHON="3.12"
SENTINEL_PYTHON="3.13"
FREQTRADE_VERSION="2026.8"
# Kev serving code (Apache-2.0, github.com/jaredpalmer/kev). Not on PyPI (the PyPI name "kev" is another project),
# so it is installed from a pinned GitHub archive (no git needed).
KEV_COMMIT="30c619b0527501cfdd448cb6eb9887e2af454603"
MIN_MACOS=14
MIN_FREE_GB=12
INSTALLER_VERSION="1"

# ---------------------------------------------------------------- output helpers
if [ -t 1 ]; then B=$'\033[1m'; G=$'\033[32m'; Y=$'\033[33m'; R=$'\033[31m'; D=$'\033[2m'; N=$'\033[0m'
else B=""; G=""; Y=""; R=""; D=""; N=""; fi
step() { printf '\n%s==> %s%s\n' "$B" "$*" "$N"; }
info() { printf '    %s\n' "$*"; }
ok()   { printf '    %s%s%s\n' "$G" "$*" "$N"; }
warn() { printf '    %s! %s%s\n' "$Y" "$*" "$N" >&2; }
die()  { printf '\n%sInstall stopped: %s%s\n' "$R" "$*" "$N" >&2; exit 1; }

# Questions go to the terminal even when this script arrives through a pipe (curl ... | bash).
ask_yes_no() {  # ask_yes_no "question" default(y|n) -> exit 0 for yes
  local q=$1 def=$2 ans=""
  if [ "${NOVAEON_YES:-0}" = 1 ]; then [ "$def" = y ]; return; fi
  if { exec 3</dev/tty; } 2>/dev/null; then
    printf '    %s %s ' "$q" "$([ "$def" = y ] && echo '[Y/n]' || echo '[y/N]')" >/dev/tty
    read -r ans <&3 || ans=""
    exec 3<&-
  fi
  case "${ans:-$def}" in [yY]*) return 0 ;; *) return 1 ;; esac
}

rand_alnum() {  # rand_alnum <length> [alphabet]: characters from /dev/urandom
  local len=$1 alphabet=${2:-A-Za-z0-9} out=""
  while [ ${#out} -lt "$len" ]; do
    out="$out$(head -c 256 /dev/urandom | LC_ALL=C tr -dc "$alphabet")"
  done
  printf '%s' "${out:0:$len}"
}

port_listener_pid() { /usr/sbin/lsof -nP -iTCP:"$1" -sTCP:LISTEN -t 2>/dev/null | head -1 || true; }
agent_pid() { launchctl list "$1" 2>/dev/null | awk -F' = ' '/"PID"/{gsub(/;/,"",$2); print $2}' || true; }

# ---------------------------------------------------------------- steps
preflight() {
  step "Checking this Mac"
  [ "$(uname -s)" = Darwin ] || die "NovaeonTradingAI runs on macOS only."
  if [ "$(uname -m)" != arm64 ]; then
    if [ "$(sysctl -n hw.optional.arm64 2>/dev/null || echo 0)" = 1 ]; then
      die "This Terminal runs under Rosetta (Intel mode). Open Terminal without Rosetta and run the command again."
    fi
    die "An Apple Silicon Mac (M1 or newer) is required. Intel Macs are not supported."
  fi
  MACOS_VERSION=$(sw_vers -productVersion); MACOS_MAJOR=${MACOS_VERSION%%.*}
  [ "$MACOS_MAJOR" -ge "$MIN_MACOS" ] || die "macOS $MIN_MACOS (Sonoma) or newer is required, this Mac has $MACOS_VERSION."
  RAM_GB=$(( $(sysctl -n hw.memsize) / 1073741824 ))
  [ "$RAM_GB" -ge 7 ] || die "At least 8 GB of memory is required, this Mac has ${RAM_GB} GB."
  if   [ "$RAM_GB" -lt 12 ]; then RAM_CLASS="8"
  elif [ "$RAM_GB" -lt 20 ]; then RAM_CLASS="16"
  elif [ "$RAM_GB" -lt 40 ]; then RAM_CLASS="24-36"
  else RAM_CLASS="48+"; fi
  mkdir -p "$H"
  local free_gb; free_gb=$(( $(df -k "$H" | awk 'NR==2{print $4}') / 1048576 ))
  local need=$MIN_FREE_GB
  if [ -n "${NOVAEON_MODEL_PATH:-}" ] || [ -f "$H/models/$HF_REPO_DIR/.novaeon-verified-${MODEL_VARIANT}.json" ]; then need=4; fi
  [ "$free_gb" -ge "$need" ] || die "Not enough free disk space: ${free_gb} GB free, about ${need} GB needed."
  ok "Apple Silicon, macOS $MACOS_VERSION, ${RAM_GB} GB memory, ${free_gb} GB free disk"
  command -v curl >/dev/null || die "curl is missing."
}

check_ports() {
  local name port label pid
  for spec in "engine:$ENGINE_PORT" "control:$CONTROL_PORT" "sentinel:$SENTINEL_PORT"; do
    name=${spec%%:*}; port=${spec##*:}; label="$LABEL_PREFIX.$name"
    pid=$(port_listener_pid "$port")
    [ -z "$pid" ] && continue
    [ "$pid" = "$(agent_pid "$label")" ] && continue   # our own service from an earlier install
    die "Port $port (needed for the $name) is used by another program (pid $pid: $(ps -o comm= -p "$pid" 2>/dev/null)).
    Close it, or choose another port, e.g. NOVAEON_$(echo "$name" | tr '[:lower:]' '[:upper:]')_PORT=$((port + 10000))."
  done
  [ "$CONTROL_PORT" = "$((ENGINE_PORT + 1))" ] || warn "The web app looks for the wallet service on port $((ENGINE_PORT + 1)) (engine port + 1); with port $CONTROL_PORT the Wallet page won't work."
}

install_uv() {
  step "Setting up uv (Python manager, private to this install)"
  UV="$H/tools/uv/uv"
  if [ -x "$UV" ] && "$UV" --version 2>/dev/null | grep -q " $UV_VERSION"; then ok "uv $UV_VERSION present"; return; fi
  mkdir -p "$H/tools/uv"
  curl -fsSL "https://astral.sh/uv/$UV_VERSION/install.sh" | env UV_UNMANAGED_INSTALL="$H/tools/uv" UV_NO_MODIFY_PATH=1 sh >/dev/null 2>&1 \
    || die "Could not download uv from astral.sh (check your internet connection)."
  [ -x "$UV" ] || die "uv install failed."
  ok "$("$UV" --version)"
}

fetch_source() {
  step "Getting NovaeonTradingAI"
  local here="" tmp
  # Run from a checkout (./install.sh)? Then install that checkout instead of downloading.
  if [ -n "${BASH_SOURCE[0]:-}" ] && [ -f "${BASH_SOURCE[0]}" ]; then
    here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
    [ -d "$here/bot" ] && [ -d "$here/installer" ] || here=""
  fi
  tmp="$H/src.new"; rm -rf "$tmp"; mkdir -p "$tmp"
  if [ -n "$here" ] && [ -z "${NOVAEON_SRC_URL:-}" ]; then
    CHECKOUT="$here"
    tar -C "$here" -cf - --exclude ./node_modules --exclude ./.git --exclude ./dist --exclude ./installer/build . | tar -C "$tmp" -xf -
    info "from local checkout $here"
  else
    CHECKOUT=""
    local url=${NOVAEON_SRC_URL:-"https://codeload.github.com/$GITHUB_REPO/tar.gz/$REF"}
    curl -fsSL --retry 3 "$url" | tar -C "$tmp" -xzf - --strip-components 1 \
      || die "Could not download $url"
    info "from $url"
  fi
  [ -f "$tmp/bot/bin/run-bot.sh" ] && [ -f "$tmp/installer/lib/novaeon_setup.py" ] || die "Downloaded source is incomplete."
  rm -rf "$H/src"; mv "$tmp" "$H/src"; SRC="$H/src"
  VERSION=$(sed -n 's/^ *"version": *"\([^"]*\)".*/\1/p' "$SRC/package.json" | head -1)
  ok "NovaeonTradingAI ${VERSION:-?} ($REF)"
}

setup_python() {
  step "Installing the trading engine (Python $ENGINE_PYTHON, Freqtrade $FREQTRADE_VERSION)"
  export UV_PYTHON_INSTALL_DIR="$H/tools/python" UV_CACHE_DIR="${NOVAEON_UV_CACHE_DIR:-$H/.cache/uv}" \
         UV_PYTHON_PREFERENCE=only-managed UV_NO_CONFIG=1 UV_NO_PROGRESS=1
  unset VIRTUAL_ENV PYTHONPATH PYTHONHOME || true
  if ! "$H/.venv/bin/python" -c "import sys; assert sys.version.startswith('$ENGINE_PYTHON')" 2>/dev/null; then
    rm -rf "$H/.venv"; "$UV" venv -q --python "$ENGINE_PYTHON" "$H/.venv"
  fi
  "$UV" pip install -q --python "$H/.venv/bin/python" -c "$SRC/installer/constraints-engine.txt" \
    "freqtrade==$FREQTRADE_VERSION" coincurve httpx fastapi uvicorn || die "Engine install failed (see above)."
  PY="$H/.venv/bin/python"
  ok "$("$H/.venv/bin/freqtrade" --version 2>/dev/null | tail -1)"

  step "Installing the Sentinel model server (Python $SENTINEL_PYTHON, MLX)"
  if ! "$H/sentinel/.venv/bin/python" -c "import sys; assert sys.version.startswith('$SENTINEL_PYTHON')" 2>/dev/null; then
    rm -rf "$H/sentinel/.venv"; mkdir -p "$H/sentinel"; "$UV" venv -q --python "$SENTINEL_PYTHON" "$H/sentinel/.venv"
  fi
  "$UV" pip install -q --python "$H/sentinel/.venv/bin/python" -c "$SRC/installer/constraints-sentinel.txt" \
    "kev[serve] @ https://github.com/jaredpalmer/kev/archive/$KEV_COMMIT.tar.gz" || die "Sentinel server install failed (see above)."
  rm -rf "$H/sentinel/sentinel"; cp -R "$SRC/novaeon-kev/sentinel" "$H/sentinel/sentinel"
  find "$H/sentinel/sentinel" -name '*.bak*' -delete
  ok "kev ${KEV_COMMIT:0:7} + $("$H/sentinel/.venv/bin/python" -c 'import mlx.core as m; print("mlx", m.__version__)')"
}

install_files() {
  step "Installing strategies, settings and services"
  mkdir -p "$H/bin" "$H/logs" "$H/user_data"
  cp "$SRC"/bot/bin/*.py "$SRC"/bot/bin/run-bot.sh "$H/bin/"
  # macOS without Xcode tools has no real /usr/bin/python3 (it opens an install dialog): use our own Python.
  # shellcheck disable=SC2016  # $PWD is meant literally: run-bot.sh expands it
  sed -i '' 's|^PY=/usr/bin/python3$|PY="$PWD/.venv/bin/python"|' "$H/bin/run-bot.sh"
  cp "$SRC/installer/lib/ensure-engine-patches.sh" "$SRC/installer/novaeon" "$SRC/installer/uninstall.sh" "$H/bin/"
  chmod +x "$H"/bin/*.sh "$H/bin/novaeon"
  (cd "$H" && .venv/bin/freqtrade create-userdir --userdir user_data >/dev/null 2>&1) || die "Could not create user_data."
  cp "$SRC"/bot/strategies/*.py "$H/user_data/strategies/"
  cp "$SRC/bot/config/config.json" "$SRC/bot/config/exchange-hyperliquid.json" "$H/user_data/"
  "$PY" "$SRC/installer/lib/novaeon_setup.py" configure --home "$H" --example "$SRC/bot/config/bot.example.json" \
    --engine-port "$ENGINE_PORT" --ai-leverage-allowed "$AI_LEVERAGE_ALLOWED" --sentinel-build "$MODEL_VARIANT" \
    --password "$(rand_alnum 20 'A-HJ-NP-Za-km-z2-9')" --jwt "$(rand_alnum 48)" --ws-token "$(rand_alnum 32)"
  ok "settings in $H/user_data (practice money, 127.0.0.1 only, AI leverage off)"

  "$H/bin/ensure-engine-patches.sh" | sed 's/^/    /'
  install_ui
}

install_ui() {
  local ui_src="" tmp="$H/ui.new" url
  rm -rf "$tmp"; mkdir -p "$tmp"
  if [ -n "${NOVAEON_UI_DIST:-}" ]; then
    ui_src=$NOVAEON_UI_DIST
  elif [ -z "${NOVAEON_UI_URL:-}" ] && [ -n "$CHECKOUT" ] && [ -f "$CHECKOUT/dist/index.html" ]; then
    ui_src="$CHECKOUT/dist"
  fi
  if [ -n "$ui_src" ]; then
    cp -R "$ui_src"/. "$tmp/"
  else
    # Prebuilt web app from the GitHub release (built by installer/build-release.sh). Tags pin it, "main" = latest.
    case "$REF" in v[0-9]*) url="https://github.com/$GITHUB_REPO/releases/download/$REF/novaeon-ui.tar.gz" ;;
                   *) url="https://github.com/$GITHUB_REPO/releases/latest/download/novaeon-ui.tar.gz" ;; esac
    url=${NOVAEON_UI_URL:-$url}
    curl -fsSL --retry 3 -o "$H/ui.tar.gz" "$url" || die "Could not download the web app ($url)."
    local want have
    want=$(curl -fsSL --retry 3 "$url.sha256" | awk '{print $1}') || die "Could not download the web app checksum."
    have=$(shasum -a 256 "$H/ui.tar.gz" | awk '{print $1}')
    [ -n "$want" ] && [ "$want" = "$have" ] || die "Web app download is corrupt (checksum mismatch)."
    tar -C "$tmp" -xzf "$H/ui.tar.gz"; rm -f "$H/ui.tar.gz"
  fi
  [ -f "$tmp/index.html" ] || die "Web app files are incomplete."
  rm -rf "$H/ui"; mv "$tmp" "$H/ui"
  local d
  d=$(echo "$H"/.venv/lib/python3*/site-packages/freqtrade/rpc/api_server/ui)
  [ -d "$d" ] || die "Engine web folder not found ($d)."
  rm -rf "$d/installed"; cp -R "$H/ui" "$d/installed"
  [ -f "$H/ui/favicon.ico" ] && cp "$H/ui/favicon.ico" "$d/favicon.ico"
  ok "web app installed"
}

pick_model() {
  if [ -z "${NOVAEON_MODEL_VARIANT:-}" ]; then
    if [ "$RAM_GB" -ge 16 ]; then MODEL_VARIANT=$HF_SUBFOLDER_8BIT; else MODEL_VARIANT=$HF_SUBFOLDER_4BIT; fi
  else
    MODEL_VARIANT=$NOVAEON_MODEL_VARIANT
  fi
  case "$MODEL_VARIANT" in "$HF_SUBFOLDER_8BIT"|"$HF_SUBFOLDER_4BIT") ;; *) die "Unknown NOVAEON_MODEL_VARIANT $MODEL_VARIANT";; esac
  # 2x/3x AI leverage needs the 8-bit model's precision; 8 GB Macs run the 4-bit build with AI leverage locked off.
  if [ "$RAM_GB" -ge 16 ] && [ "$MODEL_VARIANT" = "$HF_SUBFOLDER_8BIT" ]; then AI_LEVERAGE_ALLOWED=true; else AI_LEVERAGE_ALLOWED=false; fi
}

fetch_model() {
  step "Getting the Novaeon Sentinel 9B model ($MODEL_VARIANT)"
  if [ -n "${NOVAEON_MODEL_PATH:-}" ]; then
    MODEL_DIR=$(cd "$NOVAEON_MODEL_PATH" && pwd) || die "NOVAEON_MODEL_PATH not found."
    for f in config.json model.safetensors head.pt tokenizer.json; do
      [ -f "$MODEL_DIR/$f" ] || die "$MODEL_DIR is not a Sentinel package (missing $f)."
    done
    ok "using local package $MODEL_DIR"; return
  fi
  local pin=$SENTINEL_4BIT_SHA256; [ "$MODEL_VARIANT" = "$HF_SUBFOLDER_8BIT" ] && pin=$SENTINEL_8BIT_SHA256
  info "download size: about $([ "$MODEL_VARIANT" = "$HF_SUBFOLDER_8BIT" ] && echo 8 || echo 4.5) GB; an interrupted download resumes when you run the installer again"
  MODEL_DIR=$(HF_HOME="$H/.cache/huggingface" HF_HUB_DISABLE_TELEMETRY=1 \
    "$H/sentinel/.venv/bin/python" "$SRC/installer/lib/fetch_model.py" --repo "$HF_REPO" --revision "$HF_REVISION" \
    --subfolder "$MODEL_VARIANT" --dest "$H/models/$HF_REPO_DIR" --pin-sha256 "$pin" | tail -1) \
    || die "Model download failed. Run the installer again to resume."
  [ -f "$MODEL_DIR/model.safetensors" ] || die "Model download incomplete."
  ok "model ready: $MODEL_DIR"
}

start_services() {
  step "Starting the background services"
  "$PY" "$SRC/installer/lib/novaeon_setup.py" plists --home "$H" --prefix "$LABEL_PREFIX" --out "$LAUNCH_AGENTS" \
    --engine-port "$ENGINE_PORT" --control-port "$CONTROL_PORT" --sentinel-port "$SENTINEL_PORT" --model-dir "$MODEL_DIR"
  if [ "${NOVAEON_START:-1}" = 0 ]; then info "not started (NOVAEON_START=0): run $H/bin/novaeon start"; return; fi
  local uid; uid=$(id -u)
  # Sentinel first: on 8 GB Macs the model should claim its memory before the engine warms up.
  for name in sentinel engine control; do
    local label="$LABEL_PREFIX.$name"
    launchctl bootout "gui/$uid/$label" 2>/dev/null || true
    local i=0; while launchctl list "$label" >/dev/null 2>&1 && [ $i -lt 20 ]; do sleep 0.5; i=$((i + 1)); done
    launchctl bootstrap "gui/$uid" "$LAUNCH_AGENTS/$label.plist" || die "Could not start $label."
    info "$label started"
  done
}

health_check() {
  [ "${NOVAEON_START:-1}" = 0 ] && return 0
  step "Checking that everything answers"
  local base="http://127.0.0.1:$ENGINE_PORT" i token cfg
  for i in $(seq 1 90); do curl -fs -m 2 "$base/api/v1/ping" >/dev/null 2>&1 && break; sleep 2; done
  curl -fs -m 2 "$base/api/v1/ping" >/dev/null 2>&1 || die "The engine does not answer on $base. Log: $H/logs/engine.log"
  ok "engine answers on $base"
  local page; page=$(curl -fs -m 5 "$base/" || true)
  case "$page" in *"<html"*|*"<HTML"*) ;; *) die "The web app is not served on $base." ;; esac
  ok "web app answers"
  token=$(curl -fs -m 5 -X POST -u "admin:$(login_password)" "$base/api/v1/token/login" \
          | "$PY" -c 'import json,sys; print(json.load(sys.stdin)["access_token"])') || die "Login check failed."
  ok "login works"
  cfg=$(curl -fs -m 5 -H "Authorization: Bearer $token" "$base/api/v1/show_config" \
        | "$PY" -c 'import json,sys; c=json.load(sys.stdin); print(c.get("dry_run"), c.get("state"), c.get("strategy"))')
  case "$cfg" in True*) ok "engine runs with practice money ($cfg)" ;; *) warn "engine config: $cfg" ;; esac
  for i in $(seq 1 30); do
    curl -fs -m 3 -H "Authorization: Bearer $token" "http://127.0.0.1:$CONTROL_PORT/control/status" >/dev/null 2>&1 && break; sleep 1
  done
  if curl -fs -m 3 -H "Authorization: Bearer $token" "http://127.0.0.1:$CONTROL_PORT/control/status" >/dev/null 2>&1; then
    ok "wallet/practice service answers"
  else warn "wallet/practice service not answering yet. Log: $H/logs/control.log"; fi
  info "waiting for the Sentinel model to load (up to 5 minutes on 8 GB Macs)..."
  for i in $(seq 1 150); do curl -fs -m 2 "http://127.0.0.1:$SENTINEL_PORT/v1/models" >/dev/null 2>&1 && break; sleep 2; done
  if curl -fs -m 2 "http://127.0.0.1:$SENTINEL_PORT/v1/models" >/dev/null 2>&1; then ok "Sentinel model answers"
  else warn "Sentinel is still loading; trades wait for it. Log: $H/logs/sentinel.log"; fi
}

login_password() { sed -n 's/^password: //p' "$H/login.txt"; }

telemetry() {
  [ -f "$H/install.env" ] && return 0   # only first installs are counted
  local url=${NOVAEON_TELEMETRY_URL:-$TELEMETRY_URL}
  [ -n "$url" ] || { TELEMETRY_CHOICE=no; return 0; }   # no endpoint yet: don't ask, send nothing
  local choice=${NOVAEON_TELEMETRY:-}
  if [ -z "$choice" ]; then
    step "One question"
    info "May we count this install anonymously? We would send only: the app version, the macOS major"
    info "version and a memory size class (e.g. \"16\"), once. No IDs, no personal data, nothing else."
    if ask_yes_no "Send the anonymous install count?" n; then choice=yes; else choice=no; fi
  fi
  TELEMETRY_CHOICE=$choice
  [ "$choice" = yes ] || return 0
  curl -fsS -m 5 -o /dev/null -H 'content-type: application/json' \
    --data "{\"event\":\"install\",\"version\":\"${VERSION:-unknown}\",\"macos_major\":$MACOS_MAJOR,\"ram_class\":\"$RAM_CLASS\"}" \
    "$url" >/dev/null 2>&1 || true
}

save_env() {
  {
    echo "# NovaeonTradingAI install settings (read by bin/novaeon, bin/uninstall.sh and the next update)"
    printf 'NOVAEON_HOME=%q\n' "$H"
    printf 'NOVAEON_ENGINE_PORT=%q\nNOVAEON_CONTROL_PORT=%q\nNOVAEON_SENTINEL_PORT=%q\n' "$ENGINE_PORT" "$CONTROL_PORT" "$SENTINEL_PORT"
    printf 'NOVAEON_LABEL_PREFIX=%q\nNOVAEON_LAUNCH_AGENTS=%q\nNOVAEON_REF=%q\n' "$LABEL_PREFIX" "$LAUNCH_AGENTS" "$REF"
    printf 'NOVAEON_MODEL_VARIANT=%q\nNOVAEON_MODEL_DIR=%q\n' "$MODEL_VARIANT" "$MODEL_DIR"
    [ -n "${NOVAEON_MODEL_PATH:-}" ] && printf 'NOVAEON_MODEL_PATH=%q\n' "$NOVAEON_MODEL_PATH"
    printf 'NOVAEON_TELEMETRY=%q\nNOVAEON_VERSION=%q\nNOVAEON_INSTALLED_AT=%q\n' "${TELEMETRY_CHOICE:-no}" "${VERSION:-}" "$(date +%Y-%m-%dT%H:%M:%S%z)"
  } > "$H/install.env.new"
  mv "$H/install.env.new" "$H/install.env"
}

finish() {
  local url="http://127.0.0.1:$ENGINE_PORT"
  printf '\n%s%sNovaeonTradingAI is %s.%s\n\n' "$B" "$G" "$([ "$UPDATE" = 1 ] && echo updated || echo installed)" "$N"
  printf '  Open:      %s%s%s\n' "$B" "$url" "$N"
  printf '  Username:  %sadmin%s\n' "$B" "$N"
  printf '  Password:  %s%s%s   (also in %s/login.txt)\n' "$B" "$(login_password)" "$N" "$H"
  printf '\n  Practice money is on: the bot trades with pretend funds until you switch to real money in the app.\n'
  printf '  Helper:    %s/bin/novaeon status | start | stop | logs | password | update | uninstall\n\n' "$H"
  if [ "${NOVAEON_START:-1}" != 0 ] && [ "${NOVAEON_NO_OPEN:-0}" != 1 ]; then
    login_password | pbcopy 2>/dev/null && printf '  (The password is on your clipboard.)\n\n'
    open "$url" 2>/dev/null || true
  fi
}

main() {
  exec </dev/null   # when piped from curl, stdin is this script: nothing below may read it
  H=${NOVAEON_HOME:-$HOME/NovaeonTradingAI}
  H=${H%/}
  UPDATE=0
  if [ -f "$H/install.env" ]; then
    UPDATE=1
    # keep the previous ports/labels/model unless overridden now
    eval "$(grep -E '^NOVAEON_(ENGINE_PORT|CONTROL_PORT|SENTINEL_PORT|LABEL_PREFIX|LAUNCH_AGENTS|REF|MODEL_VARIANT|MODEL_PATH|TELEMETRY)=' "$H/install.env" \
      | sed 's/^\([A-Z_]*\)=/PREV_\1=/')"
  fi
  ENGINE_PORT=${NOVAEON_ENGINE_PORT:-${PREV_NOVAEON_ENGINE_PORT:-8081}}
  CONTROL_PORT=${NOVAEON_CONTROL_PORT:-${PREV_NOVAEON_CONTROL_PORT:-$((ENGINE_PORT + 1))}}
  SENTINEL_PORT=${NOVAEON_SENTINEL_PORT:-${PREV_NOVAEON_SENTINEL_PORT:-8010}}
  LABEL_PREFIX=${NOVAEON_LABEL_PREFIX:-${PREV_NOVAEON_LABEL_PREFIX:-studio.novaeon.trading}}
  LAUNCH_AGENTS=${NOVAEON_LAUNCH_AGENTS:-${PREV_NOVAEON_LAUNCH_AGENTS:-$HOME/Library/LaunchAgents}}
  REF=${NOVAEON_REF:-${PREV_NOVAEON_REF:-$DEFAULT_REF}}
  NOVAEON_MODEL_VARIANT=${NOVAEON_MODEL_VARIANT:-${PREV_NOVAEON_MODEL_VARIANT:-}}
  NOVAEON_MODEL_PATH=${NOVAEON_MODEL_PATH:-${PREV_NOVAEON_MODEL_PATH:-}}
  [ "$UPDATE" = 1 ] && TELEMETRY_CHOICE=${PREV_NOVAEON_TELEMETRY:-no}
  HF_REPO_DIR=$(echo "$HF_REPO" | tr '/' '_')
  RAM_GB=$(( $(sysctl -n hw.memsize) / 1073741824 ))

  printf '%sNovaeonTradingAI installer%s %s(installer v%s, target %s)%s\n' "$B" "$N" "$D" "$INSTALLER_VERSION" "$H" "$N"
  [ "$UPDATE" = 1 ] && info "existing install found: updating it (settings, trades and login are kept)"
  pick_model
  preflight
  check_ports
  install_uv
  fetch_source
  setup_python
  install_files
  fetch_model
  start_services
  health_check
  telemetry
  save_env
  finish
}

main "$@"
