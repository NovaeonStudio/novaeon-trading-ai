#!/bin/bash
# NovaeonTradingAI installer for Apple Silicon Macs (macOS 14+) and Linux (x86_64 / arm64, systemd), also inside WSL2.
#
#   curl -fsSL https://raw.githubusercontent.com/NovaeonStudio/novaeon-trading-ai/main/install.sh | bash
#   curl -fsSL .../install.sh | bash -s -- --sentinel remote --sentinel-url http://<mac>:8010     (options: see --help)
#
# Installs everything into ~/NovaeonTradingAI (or $NOVAEON_HOME): its own uv + Python, the trading engine, the web app,
# the Novaeon Sentinel model (or a link to one on another machine) and background services (launchd agents on macOS,
# systemd user services on Linux). No Homebrew, no Xcode tools, no sudo. Running it again updates an existing install
# and keeps your settings, trades and login.
#
# Defaults: practice money (no real funds), a random login password, the app only reachable from this computer
# (127.0.0.1), leverage 1x. Nothing is sent anywhere unless you opt in to the anonymous install count (macOS).
#
# Sentinel (the news check before every buy) - NOVAEON_SENTINEL_MODE or --sentinel <mode>:
#   mlx     on this Mac (macOS default): 8-bit build with >= 16 GB memory, 4-bit on 8 GB Macs
#   remote  on another machine in your private network (split setup): --sentinel-url http://<mac>:8010/v1/systemone
#   cuda    on this computer's NVIDIA GPU (Linux, EXPERIMENTAL): 24 GB graphics memory, Kev's torch backend, bf16
#   cpu     on this computer's processor (Linux, EXPERIMENTAL, not recommended: 1-3 min per check on most CPUs): ~20 GB memory
#   off     no news check: the bot trades at 1x without it
#   Linux default: remote if a URL is given, else cuda if an NVIDIA GPU with enough memory is found, else a question
#   (without a terminal: off).
# --sentinel-only: install just the Sentinel model server (e.g. on a Mac that serves a bot on a Linux/Windows machine).
#
# Environment overrides (all optional):
#   NOVAEON_HOME            install directory                       (default ~/NovaeonTradingAI; Sentinel only: ~/NovaeonSentinel)
#   NOVAEON_ENGINE_PORT     web app + engine API port               (default 8081)
#   NOVAEON_CONTROL_PORT    wallet/practice-money service port      (default: engine port + 1; the web app expects that)
#   NOVAEON_SENTINEL_PORT   Sentinel model server port              (default 8010)
#   NOVAEON_LABEL_PREFIX    service name prefix                     (default studio.novaeon.trading on macOS, novaeon-trading on Linux)
#   NOVAEON_REF             git branch or tag to install            (default main)
#   NOVAEON_SENTINEL_MODE   mlx | remote | cuda | cpu | off         (see above)
#   NOVAEON_SENTINEL_URL    the remote Sentinel (mode remote)
#   NOVAEON_SENTINEL_ONLY=1 same as --sentinel-only
#   NOVAEON_SENTINEL_BIND   Sentinel only: listen on this address instead of 127.0.0.1 (opt-in; prefer tailscale serve)
#   NOVAEON_SENTINEL_FORCE=1  skip the memory / graphics-memory checks of the cuda and cpu modes
#   NOVAEON_MODEL_VARIANT   mlx-8bit | mlx-4bit                     (default: by RAM, >=16 GB -> 8-bit)
#   NOVAEON_MODEL_PATH      use an existing local Sentinel package (mlx) or LoRA run (cuda/cpu) instead of downloading it
#   NOVAEON_SRC_URL / NOVAEON_UI_URL / NOVAEON_UI_DIST   alternative source / web-app locations (testing, mirrors)
#   NOVAEON_TELEMETRY       yes | no: answer the install-count question without asking
#   NOVAEON_NO_OPEN=1       don't open the browser or copy the password at the end
#   NOVAEON_START=0         install/update only, don't (re)start the services (start later: bin/novaeon start)
#   NOVAEON_YES=1           non-interactive: accept defaults for every question
set -euo pipefail

# ---------------------------------------------------------------- constants (release engineering edits these)
GITHUB_REPO="NovaeonStudio/novaeon-trading-ai"
DEFAULT_REF="main"
HF_REPO="NovaeonStudio/novaeon-sentinel-9b"   # Hugging Face model repo (Sentinel MLX packages + LoRA)
HF_REVISION="main"
HF_SUBFOLDER_8BIT="mlx-8bit"                   # >= 16 GB RAM
HF_SUBFOLDER_4BIT="mlx-4bit"                   # 8 GB RAM (AI leverage locked off)
HF_SUBFOLDER_LORA="lora"                       # cuda / cpu: Kev's torch backend on top of the base model below
SENTINEL_8BIT_SHA256="373bc466f1b795a080490dff3d4b952293909d930b9d053a09c8038250b1ea8a"   # pin of <subfolder>/model.safetensors (release 1.0.0)
SENTINEL_4BIT_SHA256="9dbad3f4805cfd62eb3a0319f06ab15d8dd87206a6ef961f6be7d7358706837a"
SENTINEL_LORA_SHA256="eaa6ec87ba68bb30b4a4a65f21a90d16cbdf7ca558ff8a2f8bc47ace65d02c60"   # pin of lora/adapter_model.safetensors
BASE_REPO="Qwen/Qwen3.5-9B-Base"               # base of the LoRA (lora/head.pt names it); bf16, 19.3 GB
BASE_REVISION="68c46c4b3498877f3ef123c856ecfde50c39f404"   # the snapshot Sentinel was trained on
FLA_VERSION="0.5.2"                            # flash-linear-attention, as in Kev's CUDA serving image
TELEMETRY_URL="https://novaeon.studio/api/install-count"   # opt-in install count endpoint (macOS installs only); empty = never asked, nothing sent
UV_VERSION="0.12.17"
ENGINE_PYTHON="3.12"
SENTINEL_PYTHON="3.13"
FREQTRADE_VERSION="2026.8"
# Kev serving code (Apache-2.0, github.com/jaredpalmer/kev). Not on PyPI (the PyPI name "kev" is another project),
# so it is installed from a pinned GitHub archive (no git needed).
KEV_COMMIT="30c619b0527501cfdd448cb6eb9887e2af454603"
MIN_MACOS=14
MIN_FREE_GB=12
CUDA_MIN_VRAM_MIB=22000    # bf16 9B backbone ~17 GB + adapter, pointer head and activations: a 24 GB card (eager passes)
CUDA_GRAPHS_MIN_VRAM_MIB=30000   # Kev's CUDA graphs add several GB of fixed buffers (Kev: ~3 GB for 9B) on top: 32 GB+ cards
CPU_MIN_RAM_GB=20          # bf16 backbone in main memory (~18 GB) plus the engine; 24 GB+ recommended
CPU_SENTINEL_TIMEOUT=240   # seconds the engine waits for a CPU Sentinel answer (measured: bf16 matmuls ~90 GFLOPS on a
                           # 6-core AVX2 laptop CPU -> 1-3 minutes per news check; CPUs with AMX / AVX512-BF16 are much faster)
SYSTEMD_CREDS_MIN=256      # `systemd-creds --user` (the Linux key store for real-money mode) needs systemd 256+
INSTALLER_VERSION="2"

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

ask_line() {  # ask_line "question" default -> prints the answer (the default without a terminal or with NOVAEON_YES=1)
  local q=$1 def=$2 ans=""
  if [ "${NOVAEON_YES:-0}" != 1 ] && { exec 3</dev/tty; } 2>/dev/null; then
    printf '    %s ' "$q" >/dev/tty
    read -r ans <&3 || ans=""
    exec 3<&-
  fi
  printf '%s' "${ans:-$def}"
}

has_tty() { [ "${NOVAEON_YES:-0}" != 1 ] && { exec 3</dev/tty; } 2>/dev/null && exec 3<&-; }

rand_alnum() {  # rand_alnum <length> [alphabet]: characters from /dev/urandom
  local len=$1 alphabet=${2:-A-Za-z0-9} out=""
  while [ ${#out} -lt "$len" ]; do
    out="$out$(head -c 256 /dev/urandom | LC_ALL=C tr -dc "$alphabet")"
  done
  printf '%s' "${out:0:$len}"
}

sha256_of() { if command -v shasum >/dev/null 2>&1; then shasum -a 256 "$1"; else sha256sum "$1"; fi | awk '{print $1}'; }

port_listener_pid() {  # pid listening on TCP port $1 ("?" when something listens but its pid is not visible), else ""
  if [ "$OS" = Darwin ]; then /usr/sbin/lsof -nP -iTCP:"$1" -sTCP:LISTEN -t 2>/dev/null | head -1 || true; return; fi
  if command -v ss >/dev/null 2>&1; then
    local line; line=$(ss -Hltnp "( sport = :$1 )" 2>/dev/null | head -1)
    [ -z "$line" ] && return 0
    case "$line" in *pid=*) printf '%s\n' "$line" | sed 's/.*pid=\([0-9]*\).*/\1/' ;; *) echo "?" ;; esac
  elif command -v lsof >/dev/null 2>&1; then lsof -nP -iTCP:"$1" -sTCP:LISTEN -t 2>/dev/null | head -1 || true
  fi
}

# Services: launchd agents <prefix>.<name> on macOS, systemd user units <prefix>-<name>.service on Linux.
svc_id() { if [ "$OS" = Darwin ]; then echo "$LABEL_PREFIX.$1"; else echo "$LABEL_PREFIX-$1.service"; fi; }
svc_pid() {
  if [ "$OS" = Darwin ]; then
    launchctl list "$(svc_id "$1")" 2>/dev/null | awk -F' = ' '/"PID"/{gsub(/;/,"",$2); print $2}' || true
  else
    local p; p=$(systemctl --user show -p MainPID --value "$(svc_id "$1")" 2>/dev/null || true)
    [ "${p:-0}" != 0 ] && echo "$p"; true
  fi
}

mem_gb() {  # physical memory in GB (rounded to the nearest GB on Linux, where MemTotal is a little below the RAM size)
  if [ "$OS" = Darwin ]; then echo $(( $(sysctl -n hw.memsize) / 1073741824 ))
  else awk '/^MemTotal:/{printf "%d\n", ($2 + 524288) / 1048576}' /proc/meminfo; fi
}

sentinel_local() { case "$SENTINEL_MODE" in mlx|cuda|cpu) return 0 ;; *) return 1 ;; esac; }
has_service() { case " $SERVICES " in *" $1 "*) return 0 ;; *) return 1 ;; esac; }

usage() {
  sed -n '2,/^set -euo/p' "${BASH_SOURCE[0]:-/dev/null}" 2>/dev/null | sed -e '$d' -e 's/^# \{0,1\}//' || true
  cat <<'EOF'

Options:
  --sentinel <mlx|remote|cuda|cpu|off>   where the news check runs (default: see above)
  --sentinel-url <url>                   the remote Sentinel, e.g. http://100.101.102.103:8010/v1/systemone
  --sentinel-only                        install only the Sentinel model server
  --yes                                  accept every default (no questions)
EOF
}

parse_args() {
  while [ $# -gt 0 ]; do
    case $1 in
      --sentinel|--sentinel-mode) [ $# -ge 2 ] || die "$1 needs a value (mlx, remote, cuda, cpu or off)"; NOVAEON_SENTINEL_MODE=$2; shift ;;
      --sentinel=*|--sentinel-mode=*) NOVAEON_SENTINEL_MODE=${1#*=} ;;
      --sentinel-url) [ $# -ge 2 ] || die "--sentinel-url needs a value"; NOVAEON_SENTINEL_URL=$2; shift ;;
      --sentinel-url=*) NOVAEON_SENTINEL_URL=${1#*=} ;;
      --sentinel-only) NOVAEON_SENTINEL_ONLY=1 ;;
      --yes|-y) NOVAEON_YES=1 ;;
      -h|--help) usage; exit 0 ;;
      *) die "unknown option $1 (see: bash install.sh --help)" ;;
    esac
    shift
  done
}

# ---------------------------------------------------------------- steps
preflight() {
  if [ "$OS" = Darwin ]; then preflight_mac; else preflight_linux; fi
  command -v curl >/dev/null || die "curl is missing."
}

preflight_mac() {
  step "Checking this Mac"
  if [ "$(uname -m)" != arm64 ]; then
    if [ "$(sysctl -n hw.optional.arm64 2>/dev/null || echo 0)" = 1 ]; then
      die "This Terminal runs under Rosetta (Intel mode). Open Terminal without Rosetta and run the command again."
    fi
    die "An Apple Silicon Mac (M1 or newer) is required. Intel Macs are not supported."
  fi
  MACOS_VERSION=$(sw_vers -productVersion); MACOS_MAJOR=${MACOS_VERSION%%.*}
  [ "$MACOS_MAJOR" -ge "$MIN_MACOS" ] || die "macOS $MIN_MACOS (Sonoma) or newer is required, this Mac has $MACOS_VERSION."
  [ "$RAM_GB" -ge 7 ] || die "At least 8 GB of memory is required, this Mac has ${RAM_GB} GB."
  ram_class
  local free_gb; free_gb=$(disk_free_gb)
  local need; need=$(disk_need_gb)
  [ "$free_gb" -ge "$need" ] || die "Not enough free disk space: ${free_gb} GB free, about ${need} GB needed."
  ok "Apple Silicon, macOS $MACOS_VERSION, ${RAM_GB} GB memory, ${free_gb} GB free disk"
}

ram_class() {
  if   [ "$RAM_GB" -lt 12 ]; then RAM_CLASS="8"
  elif [ "$RAM_GB" -lt 20 ]; then RAM_CLASS="16"
  elif [ "$RAM_GB" -lt 40 ]; then RAM_CLASS="24-36"
  else RAM_CLASS="48+"; fi
}

disk_free_gb() { mkdir -p "$H"; echo $(( $(df -k "$H" | awk 'NR==2{print $4}') / 1048576 )); }

disk_need_gb() {  # rough free space the chosen mode needs (the model downloads dominate)
  case "$SENTINEL_MODE" in
    mlx) if [ -n "${NOVAEON_MODEL_PATH:-}" ] || [ -f "$H/models/$HF_REPO_DIR/.novaeon-verified-${MODEL_VARIANT}.json" ]; then echo 4; else echo "$MIN_FREE_GB"; fi ;;
    cuda|cpu) if ls "$H/models/.novaeon-verified-$(echo "$BASE_REPO" | tr '/' '_')-"* >/dev/null 2>&1; then echo 10
              elif [ "$SENTINEL_MODE" = cuda ]; then echo 30; else echo 26; fi ;;
    *) echo 4 ;;
  esac
}

preflight_linux() {
  step "Checking this computer"
  ARCH=$(uname -m)
  case "$ARCH" in x86_64|aarch64) ;; *) die "Linux on x86_64 or arm64 (aarch64) is required, this computer is $ARCH." ;; esac
  if ldd --version 2>&1 | grep -qi musl; then die "musl-based Linux (e.g. Alpine) is not supported: a glibc distribution is required."; fi
  # shellcheck disable=SC1091
  OS_NAME=$( (. /etc/os-release && echo "${PRETTY_NAME:-Linux}") 2>/dev/null || echo Linux)
  WSL=0; grep -qiE 'microsoft|wsl' /proc/sys/kernel/osrelease 2>/dev/null && WSL=1
  command -v systemctl >/dev/null 2>&1 || die "systemd is required (the bot runs as systemd user services)."
  if ! systemctl --user show-environment >/dev/null 2>&1; then
    if [ "$WSL" = 1 ]; then
      die "systemd is not running in this WSL distribution. Add to /etc/wsl.conf:
      [boot]
      systemd=true
    then run 'wsl --shutdown' in Windows and start the installer again (the Windows installer does this for you)."
    fi
    die "systemd user services are not available in this session. Log in directly or over ssh as $(id -un)
    (not through 'su' or 'sudo'), then run the installer again."
  fi
  SYSTEMD_VERSION=$(systemctl --version 2>/dev/null | awk 'NR==1{print $2+0}')
  [ "$RAM_GB" -ge 2 ] || die "At least 2 GB of memory is required, this computer has ${RAM_GB} GB."
  local free_gb; free_gb=$(disk_free_gb)
  local need; need=$(disk_need_gb)
  [ "$free_gb" -ge "$need" ] || die "Not enough free disk space: ${free_gb} GB free, about ${need} GB needed."
  ok "$OS_NAME ($ARCH$([ "$WSL" = 1 ] && echo ', WSL2')), systemd ${SYSTEMD_VERSION:-?}, ${RAM_GB} GB memory, ${free_gb} GB free disk"
  command -v tar >/dev/null || die "tar is missing."
  if [ "$KIND" = full ] && [ "${SYSTEMD_VERSION:-0}" -lt "$SYSTEMD_CREDS_MIN" ]; then
    warn "systemd ${SYSTEMD_VERSION:-?} is older than $SYSTEMD_CREDS_MIN: practice money works, but real-money mode cannot"
    warn "store the bot key securely here (needs 'systemd-creds --user', e.g. Ubuntu 25.04+, Debian 13, Fedora 41+)."
  fi
  check_linger
}

check_linger() {
  local user; user=$(id -un)
  [ "$(loginctl show-user "$user" -p Linger --value 2>/dev/null || echo unknown)" = yes ] && return 0
  info "Linux stops a user's background services when that user logs out, unless 'linger' is on for the user."
  if ask_yes_no "Keep NovaeonTradingAI running when you are logged out (turn on linger for $user)?" y \
     && loginctl enable-linger "$user" </dev/null >/dev/null 2>&1; then
    ok "linger on: the services keep running after you log out and start when the computer starts"
  else
    warn "linger is off: the bot stops when you log out. Turn it on later with: sudo loginctl enable-linger $user"
  fi
}

detect_gpu() {  # GPU_NAME / GPU_MIB of the NVIDIA GPU with the most memory, if any
  GPU_NAME=""; GPU_MIB=0
  local smi; smi=$(command -v nvidia-smi 2>/dev/null || true)
  [ -z "$smi" ] && [ -x /usr/lib/wsl/lib/nvidia-smi ] && smi=/usr/lib/wsl/lib/nvidia-smi
  [ -n "$smi" ] || return 0
  local line; line=$("$smi" --query-gpu=memory.total,name --format=csv,noheader,nounits 2>/dev/null | sort -t, -k1 -n -r | head -1 || true)
  [ -n "$line" ] || return 0
  GPU_MIB=$(printf '%s' "${line%%,*}" | tr -dc 0-9); GPU_MIB=${GPU_MIB:-0}
  GPU_NAME=$(printf '%s' "${line#*,}" | sed 's/^ *//')
}

normalize_url() {  # http://host:8010 -> http://host:8010/v1/systemone
  local u=$1
  case "$u" in http://*|https://*) ;; *) u="http://$u" ;; esac
  u=${u%/}
  case "$u" in */v1/*) ;; *) u="$u/v1/systemone" ;; esac
  printf '%s' "$u"
}

resolve_sentinel() {
  local mode=${NOVAEON_SENTINEL_MODE:-}
  SENTINEL_URL=${NOVAEON_SENTINEL_URL:-${PREV_NOVAEON_SENTINEL_URL:-}}
  if [ -z "$mode" ] && [ -n "${NOVAEON_SENTINEL_URL:-}" ]; then mode=remote; fi
  [ -z "$mode" ] && mode=${PREV_NOVAEON_SENTINEL_MODE:-}
  if [ "$OS" = Darwin ]; then
    mode=${mode:-mlx}
    case "$mode" in mlx|remote|off) ;; cuda|cpu) die "Sentinel mode $mode is for Linux; on a Mac Sentinel runs on Apple's GPU (mode mlx)." ;;
                    *) die "Unknown Sentinel mode '$mode' (mlx, remote or off on a Mac)." ;; esac
  else
    case "$mode" in remote|cuda|cpu|off|"") ;; mlx) die "Sentinel mode mlx needs an Apple Silicon Mac; on Linux use cuda, cpu, remote or off." ;;
                    *) die "Unknown Sentinel mode '$mode' (remote, cuda, cpu or off on Linux)." ;; esac
    if [ -z "$mode" ]; then
      detect_gpu
      if [ "$GPU_MIB" -ge "$CUDA_MIN_VRAM_MIB" ]; then
        mode=cuda
        info "NVIDIA GPU found ($GPU_NAME, $((GPU_MIB / 1024)) GB): Sentinel will run on it (experimental)."
      else
        [ "$KIND" = sentinel-only ] && die "Sentinel only needs a local mode: --sentinel cuda or --sentinel cpu (both experimental)."
        mode=$(ask_sentinel_mode)
      fi
    fi
  fi
  if [ "$KIND" = sentinel-only ]; then
    case "$mode" in remote|off) die "--sentinel-only installs a local Sentinel; mode '$mode' makes no sense here." ;; esac
  fi
  if [ "$mode" = remote ]; then
    if [ -z "$SENTINEL_URL" ]; then
      has_tty || die "Sentinel mode remote needs --sentinel-url http://<machine>:8010/v1/systemone (or NOVAEON_SENTINEL_URL)."
      SENTINEL_URL=$(ask_line "Sentinel URL (e.g. http://100.101.102.103:8010):" "")
      [ -n "$SENTINEL_URL" ] || die "No Sentinel URL given."
    fi
    SENTINEL_URL=$(normalize_url "$SENTINEL_URL")
  else
    SENTINEL_URL=""
  fi
  SENTINEL_MODE=$mode
}

ask_sentinel_mode() {  # Linux without a suitable GPU: ask; without a terminal the answer is "off"
  local gpu_note="No NVIDIA GPU found"
  [ "$GPU_MIB" -gt 0 ] && gpu_note="NVIDIA GPU $GPU_NAME has $((GPU_MIB / 1024)) GB, Sentinel needs a 24 GB card"
  if ! has_tty; then
    {
      info "$gpu_note and no Sentinel URL given: installing WITHOUT the news check (Sentinel mode off)."
      info "The bot then trades at 1x without Sentinel. To add it later, run the installer again with"
      info "--sentinel remote --sentinel-url http://<mac>:8010/v1/systemone (or --sentinel cpu, experimental)."
    } >&2
    echo off; return
  fi
  {
    step "Where should Sentinel (the news check before every buy) run?"
    info "$gpu_note."
    info "  1) remote - on a Mac (or GPU machine) in your private network, e.g. over Tailscale (recommended)"
    info "  2) cpu    - on this computer's processor: EXPERIMENTAL, not recommended (minutes per check on most CPUs),"
    info "              needs about 20 GB of memory (this one has ${RAM_GB} GB)"
    info "  3) off    - no news check: the bot trades at 1x without it (add Sentinel later by running the installer again)"
  } >&2
  case "$(ask_line "Choice [3]:" 3)" in
    1|remote) echo remote ;;
    2|cpu) echo cpu ;;
    *) echo off ;;
  esac
}

pick_model() {
  AI_LEVERAGE_ALLOWED=false
  case "$SENTINEL_MODE" in
    mlx)
      if [ -z "${NOVAEON_MODEL_VARIANT:-}" ]; then
        if [ "$RAM_GB" -ge 16 ]; then MODEL_VARIANT=$HF_SUBFOLDER_8BIT; else MODEL_VARIANT=$HF_SUBFOLDER_4BIT; fi
      else
        MODEL_VARIANT=$NOVAEON_MODEL_VARIANT
      fi
      case "$MODEL_VARIANT" in "$HF_SUBFOLDER_8BIT"|"$HF_SUBFOLDER_4BIT") ;; *) die "Unknown NOVAEON_MODEL_VARIANT $MODEL_VARIANT";; esac
      # 2x/3x AI leverage needs the 8-bit model's precision; 8 GB Macs run the 4-bit build with AI leverage locked off.
      if [ "$RAM_GB" -ge 16 ] && [ "$MODEL_VARIANT" = "$HF_SUBFOLDER_8BIT" ]; then AI_LEVERAGE_ALLOWED=true; fi
      SENTINEL_BUILD=$MODEL_VARIANT ;;
    cuda|cpu) MODEL_VARIANT=$HF_SUBFOLDER_LORA; SENTINEL_BUILD="$SENTINEL_MODE-bf16"; AI_LEVERAGE_ALLOWED=true ;;
    remote) MODEL_VARIANT=""; SENTINEL_BUILD="remote"; AI_LEVERAGE_ALLOWED=true ;;   # narrowed by check_remote (4-bit build)
    off) MODEL_VARIANT=""; SENTINEL_BUILD="off" ;;
  esac
}

check_local_resources() {  # cuda / cpu: enough (graphics) memory for the bf16 model?
  local force=${NOVAEON_SENTINEL_FORCE:-0}
  if [ "$SENTINEL_MODE" = cuda ]; then
    detect_gpu
    if [ "$GPU_MIB" -lt "$CUDA_MIN_VRAM_MIB" ]; then
      local msg="Sentinel mode cuda needs an NVIDIA GPU with 24 GB of memory (found: ${GPU_NAME:-none}${GPU_NAME:+, $((GPU_MIB / 1024)) GB}; is the driver installed, does 'nvidia-smi' work?)."
      if [ "$force" = 1 ]; then warn "$msg Continuing (NOVAEON_SENTINEL_FORCE=1)."; else die "$msg"; fi
    fi
    [ "$RAM_GB" -ge 24 ] || warn "The model is staged through main memory while it loads (~19 GB); with ${RAM_GB} GB this may need swap."
    warn "Sentinel on NVIDIA GPUs is EXPERIMENTAL: the 9B model has not been run on an NVIDIA GPU by us yet."
  elif [ "$SENTINEL_MODE" = cpu ]; then
    if [ "$RAM_GB" -lt "$CPU_MIN_RAM_GB" ]; then
      local msg="Sentinel mode cpu needs about 20 GB of memory (24 GB+ recommended), this computer has ${RAM_GB} GB."
      if [ "$force" = 1 ]; then warn "$msg Continuing (NOVAEON_SENTINEL_FORCE=1)."; else die "$msg Use --sentinel remote or --sentinel off."; fi
    elif [ "$RAM_GB" -lt 24 ]; then warn "${RAM_GB} GB of memory is tight for Sentinel on the CPU (24 GB+ recommended)."; fi
    if [ "$(uname -m)" = x86_64 ] && ! grep -qwE 'amx_bf16|avx512_bf16' /proc/cpuinfo 2>/dev/null; then
      warn "Sentinel on the CPU is EXPERIMENTAL and NOT RECOMMENDED here: this processor has no fast bf16 support"
      warn "(AMX or AVX512-BF16), so each news check takes about 1 to 3 minutes and the bot waits that long before a buy."
      warn "A Mac or NVIDIA GPU in your network (--sentinel remote) answers in well under a second."
    else
      warn "Sentinel on the CPU is EXPERIMENTAL and slow: expect many seconds per news check (not measured on this processor)."
    fi
  fi
}

check_ports() {
  local name port pid
  for name in $SERVICES; do
    case $name in engine) port=$ENGINE_PORT ;; control) port=$CONTROL_PORT ;; sentinel) port=$SENTINEL_PORT ;; esac
    pid=$(port_listener_pid "$port")
    [ -z "$pid" ] && continue
    [ "$pid" = "$(svc_pid "$name")" ] && continue   # our own service from an earlier install
    die "Port $port (needed for the $name) is used by another program (pid $pid: $(ps -o comm= -p "$pid" 2>/dev/null || echo '?')).
    Close it, or choose another port, e.g. NOVAEON_$(echo "$name" | tr '[:lower:]' '[:upper:]')_PORT=$((port + 10000))."
  done
  if has_service engine; then
    [ "$CONTROL_PORT" = "$((ENGINE_PORT + 1))" ] || warn "The web app looks for the wallet service on port $((ENGINE_PORT + 1)) (engine port + 1); with port $CONTROL_PORT the Wallet page won't work."
  fi
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

uv_env() {
  export UV_PYTHON_INSTALL_DIR="$H/tools/python" UV_CACHE_DIR="${NOVAEON_UV_CACHE_DIR:-$H/.cache/uv}" \
         UV_PYTHON_PREFERENCE=only-managed UV_NO_CONFIG=1 UV_NO_PROGRESS=1
  unset VIRTUAL_ENV PYTHONPATH PYTHONHOME || true
}

setup_python() {
  uv_env
  if has_service engine; then
    step "Installing the trading engine (Python $ENGINE_PYTHON, Freqtrade $FREQTRADE_VERSION)"
    if ! "$H/.venv/bin/python" -c "import sys; assert sys.version.startswith('$ENGINE_PYTHON')" 2>/dev/null; then
      rm -rf "$H/.venv"; "$UV" venv -q --python "$ENGINE_PYTHON" "$H/.venv"
    fi
    "$UV" pip install -q --python "$H/.venv/bin/python" -c "$SRC/installer/constraints-engine.txt" \
      "freqtrade==$FREQTRADE_VERSION" coincurve httpx fastapi uvicorn || die "Engine install failed (see above)."
    PY="$H/.venv/bin/python"
    ok "$("$H/.venv/bin/freqtrade" --version 2>/dev/null | tail -1)"
  fi
  if sentinel_local; then setup_sentinel; fi
  [ -n "${PY:-}" ] || PY="$H/sentinel/.venv/bin/python"   # Sentinel-only installs run the (stdlib-only) setup helper with it
}

setup_sentinel() {
  local variant=$SENTINEL_MODE extra="" backend="" venv="$H/sentinel/.venv" fla=0
  case "$SENTINEL_MODE" in
    mlx) step "Installing the Sentinel model server (Python $SENTINEL_PYTHON, MLX)" ;;
    cuda) step "Installing the Sentinel model server (Python $SENTINEL_PYTHON, PyTorch with CUDA; a few GB)"
          backend="--torch-backend=auto"
          # flash-linear-attention (Kev's fast DeltaNet kernels) compiles with Triton at run time, which needs a C compiler;
          # without one, transformers' plain PyTorch path serves the same model (slower on long news lists)
          if command -v cc >/dev/null 2>&1 || command -v gcc >/dev/null 2>&1; then fla=1; extra="flash-linear-attention==$FLA_VERSION"
          else warn "no C compiler found: installing without the fast GPU kernels (install one, e.g. 'sudo apt install build-essential', and run the installer again for them)"; fi ;;
    cpu) step "Installing the Sentinel model server (Python $SENTINEL_PYTHON, PyTorch for the CPU)"
         backend="--torch-backend=cpu" ;;
  esac
  # a different torch build (cuda <-> cpu) needs a fresh environment: uv keeps an installed torch that satisfies the pin
  if ! "$venv/bin/python" -c "import sys; assert sys.version.startswith('$SENTINEL_PYTHON')" 2>/dev/null \
     || [ "$(cat "$venv/.novaeon-variant" 2>/dev/null || echo mlx)" != "$variant" ]; then
    rm -rf "$venv"; mkdir -p "$H/sentinel"; "$UV" venv -q --python "$SENTINEL_PYTHON" "$venv"
  fi
  # shellcheck disable=SC2086  # $backend / $extra: empty or one word each
  "$UV" pip install -q --python "$venv/bin/python" $backend -c "$SRC/installer/constraints-sentinel.txt" \
    "kev[serve] @ https://github.com/jaredpalmer/kev/archive/$KEV_COMMIT.tar.gz" $extra || die "Sentinel server install failed (see above)."
  if [ "$SENTINEL_MODE" = cuda ] && [ "$fla" = 0 ]; then   # left over from a run that had a compiler: would fail to start now
    "$UV" pip uninstall -q --python "$venv/bin/python" flash-linear-attention fla-core >/dev/null 2>&1 || true
  fi
  echo "$variant" > "$venv/.novaeon-variant"
  rm -rf "$H/sentinel/sentinel"; cp -R "$SRC/novaeon-kev/sentinel" "$H/sentinel/sentinel"
  find "$H/sentinel/sentinel" -name '*.bak*' -delete
  if [ "$SENTINEL_MODE" = mlx ]; then
    ok "kev ${KEV_COMMIT:0:7} + $("$venv/bin/python" -c 'import mlx.core as m; print("mlx", m.__version__)')"
    return
  fi
  ok "kev ${KEV_COMMIT:0:7} + $("$venv/bin/python" -c 'import torch; print("torch", torch.__version__)')$([ "$fla" = 1 ] && echo " + flash-linear-attention $FLA_VERSION")"
  if [ "$SENTINEL_MODE" = cuda ] && ! "$venv/bin/python" -c 'import torch, sys; sys.exit(0 if torch.cuda.is_available() else 1)' 2>/dev/null; then
    warn "PyTorch does not see the GPU (torch.cuda.is_available() is False): check the NVIDIA driver (nvidia-smi)."
  fi
  # Service settings (rewritten on every install): Kev's CUDA serving defaults are CUDA graphs + fused kernels. The graph
  # buffers take several GB on top of the ~17 GB model, so cards under ~30 GB serve eagerly; fused kernels need fla.
  {
    echo "# Written by the installer on every install/update. Your own settings: sentinel.local.env (same format)."
    if [ "$SENTINEL_MODE" = cuda ]; then
      [ "$fla" = 1 ] || echo "KEV_FUSED=0"
      [ "${GPU_MIB:-0}" -ge "$CUDA_GRAPHS_MIN_VRAM_MIB" ] || echo "KEV_CUDA_GRAPHS=0"
      echo "PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True"
    fi
  } > "$H/sentinel/sentinel.env"
  [ -f "$H/sentinel/sentinel.local.env" ] || printf '%s\n' \
    "# Extra settings for the Sentinel service (KEY=value per line), read at every start after sentinel.env. Examples:" \
    "#   KEV_CUDA_GRAPHS=1   CUDA graphs on (faster; needs a GPU with ~30 GB+)" \
    "#   KEV_DTYPE=fp32      exact fp32 path (needs twice the memory)" > "$H/sentinel/sentinel.local.env"
}

install_files() {
  step "Installing $([ "$KIND" = full ] && echo "strategies, settings and services" || echo "the helper tools")"
  mkdir -p "$H/bin" "$H/logs"
  local f
  for f in novaeon uninstall.sh; do   # new file + rename: "novaeon update" is still reading the old one while this runs
    cp "$SRC/installer/$f" "$H/bin/$f.new"; chmod +x "$H/bin/$f.new"; mv -f "$H/bin/$f.new" "$H/bin/$f"
  done
  [ "$KIND" = full ] || return 0
  mkdir -p "$H/user_data"
  cp "$SRC"/bot/bin/*.py "$SRC"/bot/bin/run-bot.sh "$H/bin/"
  # Our own Python instead of the system one (macOS without Xcode tools has no real /usr/bin/python3; Linux may lack it).
  # shellcheck disable=SC2016  # $PWD is meant literally: run-bot.sh expands it
  sed 's|^PY=/usr/bin/python3$|PY="$PWD/.venv/bin/python"|' "$H/bin/run-bot.sh" > "$H/bin/run-bot.sh.new"
  mv "$H/bin/run-bot.sh.new" "$H/bin/run-bot.sh"
  cp "$SRC/installer/lib/ensure-engine-patches.sh" "$H/bin/"
  chmod +x "$H"/bin/*.sh
  (cd "$H" && .venv/bin/freqtrade create-userdir --userdir user_data >/dev/null 2>&1) || die "Could not create user_data."
  cp "$SRC"/bot/strategies/*.py "$H/user_data/strategies/"
  cp "$SRC/bot/config/config.json" "$SRC/bot/config/exchange-hyperliquid.json" "$H/user_data/"
  "$PY" "$SRC/installer/lib/novaeon_setup.py" configure --home "$H" --example "$SRC/bot/config/bot.example.json" \
    --engine-port "$ENGINE_PORT" --ai-leverage-allowed "$AI_LEVERAGE_ALLOWED" --sentinel-build "$SENTINEL_BUILD" \
    --sentinel-mode "$SENTINEL_MODE" \
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
    have=$(sha256_of "$H/ui.tar.gz")
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

fetch_model() {
  sentinel_local || return 0
  if [ "$SENTINEL_MODE" = mlx ]; then fetch_model_mlx; else fetch_model_lora; fi
}

fetch_model_mlx() {
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

fetch_model_lora() {  # cuda / cpu: the LoRA run + its base model in a private Hugging Face cache under models/
  step "Getting the Novaeon Sentinel 9B model (LoRA + base model $BASE_REPO, bf16)"
  local hf="$H/models/huggingface"
  if [ -n "${NOVAEON_MODEL_PATH:-}" ]; then
    MODEL_DIR=$(cd "$NOVAEON_MODEL_PATH" && pwd) || die "NOVAEON_MODEL_PATH not found."
    for f in adapter_config.json adapter_model.safetensors head.pt; do
      [ -f "$MODEL_DIR/$f" ] || die "$MODEL_DIR is not a Sentinel LoRA run (missing $f)."
    done
    info "using local LoRA run $MODEL_DIR"
  else
    MODEL_DIR=$(HF_HOME="$H/.cache/huggingface" HF_HUB_DISABLE_TELEMETRY=1 \
      "$H/sentinel/.venv/bin/python" "$SRC/installer/lib/fetch_model.py" --repo "$HF_REPO" --revision "$HF_REVISION" \
      --subfolder "$HF_SUBFOLDER_LORA" --dest "$H/models/$HF_REPO_DIR" --pin-sha256 "$SENTINEL_LORA_SHA256" | tail -1) \
      || die "Model download failed. Run the installer again to resume."
    [ -f "$MODEL_DIR/head.pt" ] || die "Model download incomplete."
  fi
  info "base model: about 19 GB; an interrupted download resumes when you run the installer again"
  HF_HOME="$hf" HF_HUB_DISABLE_TELEMETRY=1 "$H/sentinel/.venv/bin/python" "$SRC/installer/lib/fetch_model.py" \
    --repo "$BASE_REPO" --revision "$BASE_REVISION" --hf-cache --dest "$H/models" >/dev/null \
    || die "Base model download failed. Run the installer again to resume."
  ok "model ready: $MODEL_DIR (+ $BASE_REPO@${BASE_REVISION:0:10})"
}

check_remote() {
  [ "$SENTINEL_MODE" = remote ] || return 0
  step "Checking the Sentinel at $SENTINEL_URL"
  local base=${SENTINEL_URL%%/v1/*} card dtype
  if card=$(curl -fsS -m 8 "$base/v1/models" 2>/dev/null); then
    dtype=$(printf '%s' "$card" | "$PY" -c 'import json,sys; m=json.load(sys.stdin)["models"][0]; print(m.get("dtype") or m.get("backend") or "")' 2>/dev/null || true)
    ok "Sentinel answers (${dtype:-model server})"
    case "$dtype" in *q4*)   # the 8 GB Mac build: less precise at picking leverage, so AI leverage stays locked
      AI_LEVERAGE_ALLOWED=false; SENTINEL_BUILD="remote mlx-q4"
      info "that is the 4-bit build: AI leverage stays locked (every trade 1x)" ;;
    *) [ -n "$dtype" ] && SENTINEL_BUILD="remote $dtype" ;;
    esac
  else
    warn "no answer from $base/v1/models. The bot is installed anyway and uses Sentinel as soon as it answers;"
    warn "until then it trades at 1x without the news check."
  fi
  local rport=${base##*:}; case "$rport" in ''|*[!0-9]*) rport=8010 ;; esac
  info "Sentinel has no login: reach it only over a private network. Recommended: Tailscale on both machines, and on"
  info "the Mac:  tailscale serve --bg --tcp $rport tcp://127.0.0.1:$rport   (then use the Mac's Tailscale address here)"
  if [ "$KIND" = full ] && [ -f "$H/user_data/novaeon.json" ]; then   # the check may have narrowed what is allowed
    "$PY" "$SRC/installer/lib/novaeon_setup.py" configure --home "$H" --example "$SRC/bot/config/bot.example.json" \
      --engine-port "$ENGINE_PORT" --ai-leverage-allowed "$AI_LEVERAGE_ALLOWED" --sentinel-build "$SENTINEL_BUILD" \
      --sentinel-mode "$SENTINEL_MODE" --password x --jwt x --ws-token x
  fi
}

engine_sentinel_url() {
  case "$SENTINEL_MODE" in
    remote) echo "$SENTINEL_URL" ;;
    off) echo off ;;
    *) echo "http://127.0.0.1:$SENTINEL_PORT/v1/systemone" ;;
  esac
}

start_services() {
  step "Starting the background services"
  local device="" hf_home="" svc_args svc_timeout=0
  case "$SENTINEL_MODE" in cuda|cpu) device=$SENTINEL_MODE; hf_home="$H/models/huggingface" ;; esac
  [ "$SENTINEL_MODE" = cpu ] && svc_timeout=$CPU_SENTINEL_TIMEOUT
  svc_args=(--home "$H" --prefix "$LABEL_PREFIX" --services "$(echo "$SERVICES" | tr ' ' ',')"
            --engine-port "$ENGINE_PORT" --control-port "$CONTROL_PORT" --sentinel-port "$SENTINEL_PORT"
            --model-dir "${MODEL_DIR:-}" --sentinel-url "$(engine_sentinel_url)" --sentinel-device "$device"
            --sentinel-host "$SENTINEL_BIND" --sentinel-timeout "$svc_timeout")
  [ -n "$hf_home" ] && svc_args+=(--hf-home "$hf_home")
  if [ "$OS" = Darwin ]; then
    "$PY" "$SRC/installer/lib/novaeon_setup.py" plists --out "$LAUNCH_AGENTS" "${svc_args[@]}"
  else
    "$PY" "$SRC/installer/lib/novaeon_setup.py" units --out "$UNIT_DIR" "${svc_args[@]}"
  fi
  remove_stale_services
  [ "$OS" = Linux ] && systemctl --user daemon-reload
  if [ "${NOVAEON_START:-1}" = 0 ]; then
    [ "$OS" = Linux ] && for name in $SERVICES; do systemctl --user enable -q "$(svc_id "$name")" 2>/dev/null || true; done
    info "not started (NOVAEON_START=0): run $H/bin/novaeon start"; return
  fi
  # Sentinel first: on 8 GB Macs the model should claim its memory before the engine warms up.
  local name label uid i
  uid=$(id -u)
  for name in sentinel engine control; do
    has_service "$name" || continue
    label=$(svc_id "$name")
    if [ "$OS" = Darwin ]; then
      launchctl bootout "gui/$uid/$label" 2>/dev/null || true
      i=0; while launchctl list "$label" >/dev/null 2>&1 && [ $i -lt 20 ]; do sleep 0.5; i=$((i + 1)); done
      launchctl bootstrap "gui/$uid" "$LAUNCH_AGENTS/$label.plist" || die "Could not start $label."
    else
      systemctl --user enable -q "$label" || die "Could not enable $label."
      systemctl --user restart "$label" || die "Could not start $label (see: systemctl --user status $label)."
    fi
    info "$label started"
  done
}

remove_stale_services() {  # services of an earlier install that this one no longer has (e.g. Sentinel moved to another machine)
  local name label uid; uid=$(id -u)
  for name in sentinel engine control; do
    has_service "$name" && continue
    label=$(svc_id "$name")
    if [ "$OS" = Darwin ]; then
      [ -f "$LAUNCH_AGENTS/$label.plist" ] || continue
      launchctl bootout "gui/$uid/$label" 2>/dev/null || true
      rm -f "$LAUNCH_AGENTS/$label.plist"
    else
      [ -f "$UNIT_DIR/$label" ] || continue
      systemctl --user disable --now -q "$label" 2>/dev/null || true
      systemctl --user reset-failed "$label" 2>/dev/null || true
      rm -f "$UNIT_DIR/$label"
    fi
    info "removed $label (not part of this install any more)"
  done
}

health_check() {
  [ "${NOVAEON_START:-1}" = 0 ] && return 0
  step "Checking that everything answers"
  local i
  if has_service engine; then
    local base="http://127.0.0.1:$ENGINE_PORT" token cfg
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
  fi
  case "$SENTINEL_MODE" in
    remote) if curl -fs -m 5 "${SENTINEL_URL%%/v1/*}/v1/models" >/dev/null 2>&1; then ok "Sentinel answers at ${SENTINEL_URL%%/v1/*}"
            else warn "Sentinel at ${SENTINEL_URL%%/v1/*} does not answer: trades go ahead at 1x without the news check until it does."; fi ;;
    off) info "Sentinel is off: the bot trades at 1x without the news check." ;;
    *)
      local tries=150 note="up to 5 minutes on 8 GB Macs" sbase="http://127.0.0.1:$SENTINEL_PORT"
      case "$SENTINEL_BIND" in 127.0.0.1|0.0.0.0|::|'') ;; *) sbase="http://$SENTINEL_BIND:$SENTINEL_PORT" ;; esac
      [ "$SENTINEL_MODE" = cpu ] && { tries=450; note="up to 15 minutes on the CPU"; }
      [ "$SENTINEL_MODE" = cuda ] && { tries=300; note="up to 10 minutes: the model is loaded and the GPU warmed up"; }
      info "waiting for the Sentinel model to load ($note)..."
      for i in $(seq 1 "$tries"); do curl -fs -m 2 "$sbase/v1/models" >/dev/null 2>&1 && break; sleep 2; done
      if curl -fs -m 2 "$sbase/v1/models" >/dev/null 2>&1; then ok "Sentinel model answers"
      else warn "Sentinel is still loading; trades wait for it. Log: $H/logs/sentinel.log"; fi ;;
  esac
}

login_password() { sed -n 's/^password: //p' "$H/login.txt"; }

telemetry() {
  [ -f "$H/install.env" ] && return 0   # only first installs are counted
  # The counter knows macOS versions only: Linux / Windows installs and Sentinel-only installs are never asked or counted.
  [ "$OS" = Darwin ] && [ "$KIND" = full ] || { TELEMETRY_CHOICE=no; return 0; }
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
    printf 'NOVAEON_HOME=%q\nNOVAEON_OS=%q\nNOVAEON_INSTALL_KIND=%q\nNOVAEON_SERVICES=%q\n' "$H" "$OS" "$KIND" "$SERVICES"
    printf 'NOVAEON_ENGINE_PORT=%q\nNOVAEON_CONTROL_PORT=%q\nNOVAEON_SENTINEL_PORT=%q\n' "$ENGINE_PORT" "$CONTROL_PORT" "$SENTINEL_PORT"
    printf 'NOVAEON_LABEL_PREFIX=%q\nNOVAEON_REF=%q\n' "$LABEL_PREFIX" "$REF"
    if [ "$OS" = Darwin ]; then printf 'NOVAEON_LAUNCH_AGENTS=%q\n' "$LAUNCH_AGENTS"; else printf 'NOVAEON_UNIT_DIR=%q\n' "$UNIT_DIR"; fi
    printf 'NOVAEON_SENTINEL_MODE=%q\nNOVAEON_SENTINEL_URL=%q\nNOVAEON_SENTINEL_BIND=%q\n' "$SENTINEL_MODE" "$SENTINEL_URL" "$SENTINEL_BIND"
    printf 'NOVAEON_MODEL_VARIANT=%q\nNOVAEON_MODEL_DIR=%q\n' "$MODEL_VARIANT" "${MODEL_DIR:-}"
    [ -n "${NOVAEON_MODEL_PATH:-}" ] && printf 'NOVAEON_MODEL_PATH=%q\n' "$NOVAEON_MODEL_PATH"
    printf 'NOVAEON_TELEMETRY=%q\nNOVAEON_VERSION=%q\nNOVAEON_INSTALLED_AT=%q\n' "${TELEMETRY_CHOICE:-no}" "${VERSION:-}" "$(date +%Y-%m-%dT%H:%M:%S%z)"
  } > "$H/install.env.new"
  mv "$H/install.env.new" "$H/install.env"
}

sentinel_summary() {
  case "$SENTINEL_MODE" in
    mlx) echo "Sentinel on this Mac ($MODEL_VARIANT)" ;;
    remote) echo "Sentinel at $SENTINEL_URL" ;;
    cuda) echo "Sentinel on the NVIDIA GPU (experimental)" ;;
    cpu) echo "Sentinel on the CPU (experimental, slow)" ;;
    off) echo "off - no news check, every trade at 1x (add Sentinel: run the installer again with --sentinel remote ...)" ;;
  esac
}

tailscale_ip() {
  local ts; ts=$(command -v tailscale 2>/dev/null || true)
  [ -z "$ts" ] && [ -x /Applications/Tailscale.app/Contents/MacOS/Tailscale ] && ts=/Applications/Tailscale.app/Contents/MacOS/Tailscale
  [ -n "$ts" ] && "$ts" ip -4 2>/dev/null | head -1 || true
}

finish() {
  if [ "$KIND" = sentinel-only ]; then finish_sentinel_only; return; fi
  local url="http://127.0.0.1:$ENGINE_PORT"
  printf '\n%s%sNovaeonTradingAI is %s.%s\n\n' "$B" "$G" "$([ "$UPDATE" = 1 ] && echo updated || echo installed)" "$N"
  if [ "$OS" = Linux ] && [ "${WSL:-0}" = 1 ]; then url="http://localhost:$ENGINE_PORT"; fi
  printf '  Open:      %s%s%s\n' "$B" "$url" "$N"
  printf '  Username:  %sadmin%s\n' "$B" "$N"
  printf '  Password:  %s%s%s   (also in %s/login.txt)\n' "$B" "$(login_password)" "$N" "$H"
  printf '  News check: %s\n' "$(sentinel_summary)"
  printf '\n  Practice money is on: the bot trades with pretend funds until you switch to real money in the app.\n'
  printf '  Helper:    %s/bin/novaeon status | start | stop | logs | password | update | uninstall\n\n' "$H"
  if [ "$OS" = Linux ]; then
    if [ "${WSL:-0}" = 1 ]; then
      printf '  Windows: open the address above in your browser. The bot runs while WSL runs (see the README, "Windows").\n\n'
    elif [ -z "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]; then
      printf '  The app listens on this computer only. From your own computer, open it through an SSH tunnel\n'
      printf '  (both ports: the app and its wallet service):\n'
      printf '    ssh -L %s:127.0.0.1:%s -L %s:127.0.0.1:%s %s@<this server>     then open http://127.0.0.1:%s\n\n' \
        "$ENGINE_PORT" "$ENGINE_PORT" "$CONTROL_PORT" "$CONTROL_PORT" "$(id -un)" "$ENGINE_PORT"
    fi
  fi
  if [ "${NOVAEON_START:-1}" != 0 ] && [ "${NOVAEON_NO_OPEN:-0}" != 1 ]; then
    if [ "$OS" = Darwin ]; then
      login_password | pbcopy 2>/dev/null && printf '  (The password is on your clipboard.)\n\n'
      open "$url" 2>/dev/null || true
    elif [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ] && command -v xdg-open >/dev/null 2>&1; then
      xdg-open "$url" >/dev/null 2>&1 || true
    fi
  fi
}

finish_sentinel_only() {
  local ip; ip=$(tailscale_ip)
  printf '\n%s%sNovaeon Sentinel is %s.%s\n\n' "$B" "$G" "$([ "$UPDATE" = 1 ] && echo updated || echo installed)" "$N"
  printf '  Model server: http://%s:%s/v1/systemone   (%s)\n' "$SENTINEL_BIND" "$SENTINEL_PORT" "$(sentinel_summary)"
  printf '  Helper:       %s/bin/novaeon status | start | stop | logs | update | uninstall\n\n' "$H"
  printf '  The model server has no login, so only machines in your private network may reach it.\n'
  if [ "$SENTINEL_BIND" = 127.0.0.1 ]; then
    printf '  Recommended: Tailscale on this machine and on the bot machine, then share the port in your tailnet:\n'
    printf '    %stailscale serve --bg --tcp %s tcp://127.0.0.1:%s%s\n' "$B" "$SENTINEL_PORT" "$SENTINEL_PORT" "$N"
  fi
  printf '\n  On the bot machine, install with:\n'
  printf '    curl -fsSL https://raw.githubusercontent.com/%s/main/install.sh | bash -s -- --sentinel remote --sentinel-url %s\n\n' \
    "$GITHUB_REPO" "http://${ip:-<tailscale-ip-of-this-machine>}:$SENTINEL_PORT/v1/systemone"
}

main() {
  parse_args "$@"
  exec </dev/null   # when piped from curl, stdin is this script: nothing below may read it
  OS=$(uname -s)
  case "$OS" in Darwin|Linux) ;; *) die "NovaeonTradingAI installs on macOS and Linux (on Windows: inside WSL2, see installer/windows/install.ps1)." ;; esac
  KIND=full; [ "${NOVAEON_SENTINEL_ONLY:-0}" = 1 ] && KIND=sentinel-only
  if [ "$KIND" = full ]; then H=${NOVAEON_HOME:-$HOME/NovaeonTradingAI}; else H=${NOVAEON_HOME:-$HOME/NovaeonSentinel}; fi
  H=${H%/}
  UPDATE=0
  if [ -f "$H/install.env" ]; then
    UPDATE=1
    # keep the previous ports/labels/model/Sentinel mode unless overridden now
    eval "$(grep -E '^NOVAEON_(INSTALL_KIND|ENGINE_PORT|CONTROL_PORT|SENTINEL_PORT|LABEL_PREFIX|LAUNCH_AGENTS|UNIT_DIR|REF|MODEL_VARIANT|MODEL_PATH|TELEMETRY|SENTINEL_MODE|SENTINEL_URL|SENTINEL_BIND)=' "$H/install.env" \
      | sed 's/^\([A-Z_]*\)=/PREV_\1=/')"
    # a Sentinel-only install stays one ("novaeon update", also with another --sentinel mode); a full bot goes elsewhere
    [ "${PREV_NOVAEON_INSTALL_KIND:-full}" = sentinel-only ] && KIND=sentinel-only
    if [ "${PREV_NOVAEON_INSTALL_KIND:-full}" = full ] && [ "$KIND" = sentinel-only ]; then
      die "$H holds a full NovaeonTradingAI install, which already includes Sentinel (on 127.0.0.1:${PREV_NOVAEON_SENTINEL_PORT:-8010}).
    To serve it to other machines, share that port (see the README, split setup), or install Sentinel only elsewhere
    (default folder ~/NovaeonSentinel)."
    fi
  fi
  ENGINE_PORT=${NOVAEON_ENGINE_PORT:-${PREV_NOVAEON_ENGINE_PORT:-8081}}
  CONTROL_PORT=${NOVAEON_CONTROL_PORT:-${PREV_NOVAEON_CONTROL_PORT:-$((ENGINE_PORT + 1))}}
  SENTINEL_PORT=${NOVAEON_SENTINEL_PORT:-${PREV_NOVAEON_SENTINEL_PORT:-8010}}
  if [ "$OS" = Darwin ]; then
    def_prefix=studio.novaeon.trading; [ "$KIND" = sentinel-only ] && def_prefix=studio.novaeon.sentinel
    LAUNCH_AGENTS=${NOVAEON_LAUNCH_AGENTS:-${PREV_NOVAEON_LAUNCH_AGENTS:-$HOME/Library/LaunchAgents}}
  else
    def_prefix=novaeon-trading; [ "$KIND" = sentinel-only ] && def_prefix=novaeon-sentinel
    UNIT_DIR=${NOVAEON_UNIT_DIR:-${PREV_NOVAEON_UNIT_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user}}
  fi
  LABEL_PREFIX=${NOVAEON_LABEL_PREFIX:-${PREV_NOVAEON_LABEL_PREFIX:-$def_prefix}}
  REF=${NOVAEON_REF:-${PREV_NOVAEON_REF:-$DEFAULT_REF}}
  NOVAEON_MODEL_VARIANT=${NOVAEON_MODEL_VARIANT:-${PREV_NOVAEON_MODEL_VARIANT:-}}
  case "$NOVAEON_MODEL_VARIANT" in lora) NOVAEON_MODEL_VARIANT="" ;; esac   # recorded by cuda/cpu installs, not a choice
  NOVAEON_MODEL_PATH=${NOVAEON_MODEL_PATH:-${PREV_NOVAEON_MODEL_PATH:-}}
  SENTINEL_BIND=${NOVAEON_SENTINEL_BIND:-${PREV_NOVAEON_SENTINEL_BIND:-127.0.0.1}}
  [ "$UPDATE" = 1 ] && TELEMETRY_CHOICE=${PREV_NOVAEON_TELEMETRY:-no}
  HF_REPO_DIR=$(echo "$HF_REPO" | tr '/' '_')
  RAM_GB=$(mem_gb)

  printf '%sNovaeonTradingAI installer%s %s(installer v%s, target %s%s)%s\n' "$B" "$N" "$D" "$INSTALLER_VERSION" "$H" \
    "$([ "$KIND" = sentinel-only ] && echo ', Sentinel only')" "$N"
  [ "$UPDATE" = 1 ] && info "existing install found: updating it (settings, trades and login are kept)"
  resolve_sentinel
  if [ "$KIND" = full ]; then SERVICES="engine control"; sentinel_local && SERVICES="sentinel engine control"
  else SERVICES="sentinel"; fi
  if [ "$SENTINEL_BIND" != 127.0.0.1 ]; then
    [ "$KIND" = sentinel-only ] || die "NOVAEON_SENTINEL_BIND is for Sentinel-only installs (the bot's own Sentinel stays on 127.0.0.1)."
    warn "Sentinel will listen on $SENTINEL_BIND, not only on this machine. It has no login: anyone who can reach"
    warn "$SENTINEL_BIND:$SENTINEL_PORT can use it. Only do this on a private network (prefer 127.0.0.1 + tailscale serve)."
  fi
  pick_model
  if [ "$SENTINEL_MODE" != mlx ] || [ "$KIND" = sentinel-only ]; then info "Sentinel: $(sentinel_summary)"; fi
  preflight
  check_local_resources
  check_ports
  install_uv
  fetch_source
  setup_python
  install_files
  fetch_model
  check_remote
  start_services
  health_check
  telemetry
  save_env
  finish
}

main "$@"
