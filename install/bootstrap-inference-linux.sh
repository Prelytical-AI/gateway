#!/usr/bin/env bash
#
# Prelytical Secure SQL Gateway — GPU inference VM bootstrap (Linux)
#
# Installs Ollama, binds it for private-network access, and pulls the default model.
# Run on a Linux GPU VM on the same LAN/VPC as the SQL/gateway Windows VM.
#
# Usage:
#   sudo ./install/bootstrap-inference-linux.sh
#   sudo ./install/bootstrap-inference-linux.sh --allowed-ip 10.0.1.50
#   sudo ./install/bootstrap-inference-linux.sh --model qwen2.5-coder:7b --skip-firewall
#
set -uo pipefail

MODEL="${PRELYTICAL_MODEL:-qwen2.5-coder:7b}"
ALLOWED_IP=""
SKIP_FIREWALL=false
OLLAMA_PORT=11434

usage() {
  cat <<'EOF'
Prelytical GPU inference VM bootstrap

Options:
  --model NAME         Ollama model to pull (default: qwen2.5-coder:7b)
  --allowed-ip IP      Restrict UFW to this source IP (SQL/gateway VM private IP)
  --skip-firewall      Do not configure UFW (client manages firewall separately)
  -h, --help           Show this help

Environment:
  PRELYTICAL_MODEL     Same as --model

Example:
  sudo ./install/bootstrap-inference-linux.sh --allowed-ip 10.0.1.50
EOF
}

log() { printf '==> %s\n' "$*"; }
warn() { printf 'WARN: %s\n' "$*" >&2; }
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --model)
      [[ $# -ge 2 ]] || fail "--model requires a value"
      MODEL="$2"
      shift 2
      ;;
    --allowed-ip)
      [[ $# -ge 2 ]] || fail "--allowed-ip requires a value"
      ALLOWED_IP="$2"
      shift 2
      ;;
    --skip-firewall)
      SKIP_FIREWALL=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "Unknown option: $1 (use --help)"
      ;;
  esac
done

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  fail "Run as root: sudo $0"
fi

if [[ -f /etc/os-release ]]; then
  # shellcheck source=/dev/null
  . /etc/os-release
  log "OS: ${PRETTY_NAME:-unknown}"
else
  warn "Could not detect OS; continuing anyway."
fi

# --- GPU check ---
if command -v nvidia-smi >/dev/null 2>&1; then
  log "NVIDIA driver OK:"
  nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader | sed 's/^/    /'
elif lspci 2>/dev/null | grep -qi nvidia; then
  cat >&2 <<'EOF'
ERROR: NVIDIA GPU detected but nvidia-smi is not available.

Install drivers first (reboot may be required), then re-run this script.

  Ubuntu example:
    sudo apt update
    sudo apt install -y ubuntu-drivers-common
    sudo ubuntu-drivers autoinstall
    sudo reboot

  AWS: use a GPU AMI (e.g. Deep Learning AMI) or install NVIDIA drivers for your instance type.
EOF
  exit 1
else
  warn "No NVIDIA GPU detected. Ollama will use CPU only (slow — not recommended for production)."
  read -r -p "Continue anyway? [y/N] " reply
  [[ "${reply,,}" == "y" || "${reply,,}" == "yes" ]] || exit 1
fi

# --- Ollama install ---
if command -v ollama >/dev/null 2>&1; then
  log "Ollama already installed: $(ollama --version 2>/dev/null || echo unknown)"
else
  log "Installing Ollama (official install script)..."
  if ! curl -fsSL https://ollama.com/install.sh | sh; then
    fail "Ollama install failed. See https://ollama.com/download/linux"
  fi
fi

# --- Listen on all interfaces (private network only — lock down with firewall/SG) ---
log "Configuring Ollama to listen on 0.0.0.0:${OLLAMA_PORT}..."
mkdir -p /etc/systemd/system/ollama.service.d
cat > /etc/systemd/system/ollama.service.d/prelytical.conf <<EOF
[Service]
Environment="OLLAMA_HOST=0.0.0.0:${OLLAMA_PORT}"
EOF

systemctl daemon-reload
systemctl enable ollama
systemctl restart ollama

sleep 2
if ! systemctl is-active --quiet ollama; then
  fail "Ollama service is not running. Check: journalctl -u ollama -n 50"
fi

# --- Firewall (optional UFW) ---
if [[ "$SKIP_FIREWALL" == "true" ]]; then
  log "Skipping UFW configuration (--skip-firewall)."
elif command -v ufw >/dev/null 2>&1; then
  if [[ -n "$ALLOWED_IP" ]]; then
    log "UFW: allow TCP ${OLLAMA_PORT} from ${ALLOWED_IP} only"
    ufw allow from "$ALLOWED_IP" to any port "$OLLAMA_PORT" proto tcp comment 'Prelytical Ollama' || true
  else
    warn "No --allowed-ip provided. UFW not changed."
    warn "Ensure your cloud security group / firewall allows TCP ${OLLAMA_PORT} from the SQL VM only."
  fi
else
  log "UFW not installed; configure cloud SG / host firewall manually."
fi

# --- Model pull ---
log "Pulling model: ${MODEL} (this may take several minutes)..."
if ! ollama pull "$MODEL"; then
  fail "Failed to pull model '${MODEL}'. Check disk space and outbound internet."
fi

# --- Warmup ---
log "Warming up model..."
ollama run "$MODEL" "Return the word ok." >/dev/null 2>&1 || warn "Warmup request failed (non-fatal)."

# --- Summary ---
PRIVATE_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
[[ -z "$PRIVATE_IP" ]] && PRIVATE_IP="<this-vm-private-ip>"

cat <<EOF

================================================================================
 Prelytical GPU inference VM — ready
================================================================================

 Private IP:     ${PRIVATE_IP}
 Model URL:      http://${PRIVATE_IP}:${OLLAMA_PORT}/v1
 Model name:     ${MODEL}

 On the SQL/gateway Windows VM, set in .env (or run configure_env_wizard.ps1):

   MODEL_BASE_URL=http://${PRIVATE_IP}:${OLLAMA_PORT}/v1
   MODEL_NAME=${MODEL}

 Then verify from the SQL VM:

   .\\install\\test_ollama_connection.ps1

 Quick check from this box:

   curl -s http://127.0.0.1:${OLLAMA_PORT}/api/tags

 Security: restrict TCP ${OLLAMA_PORT} to the SQL/gateway VM private IP only.
 After model download, outbound internet on this VM can be disabled if required.

 See docs/GPU_INFERENCE_VM.md for the full client checklist.
================================================================================

EOF
