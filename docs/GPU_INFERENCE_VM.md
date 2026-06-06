# GPU Inference VM (Option 2)

Run Ollama on a **dedicated Linux GPU VM** while the Prelytical gateway stays on the **Windows SQL Server VM**. No cloud inference — data stays in the client environment.

Use this when same-VM CPU inference is too slow for production.

## What you need from the client (minimum)

| # | Question | Example answer |
|---|----------|----------------|
| 1 | Can they add a **Linux VM with a GPU** on the **same network** as SQL Server? | Yes |
| 2 | **Private IP** of the GPU VM | `10.0.2.47` |
| 3 | Can the **SQL VM** reach **TCP 11434** on that IP? | Yes (firewall/SG opened) |
| 4 | Is **one-time outbound internet** OK on the GPU VM for `ollama pull`? | Yes (optional after pull) |

You do **not** need VPC IDs, cloud vendor details, or subnet design upfront — client IT provisions the VM however they normally would.

## GPU VM requirements

| Requirement | Recommendation |
|-------------|----------------|
| OS | Ubuntu 22.04 LTS (or 24.04) |
| GPU | NVIDIA with **8 GB+ VRAM** (7B models) |
| Instance examples | AWS `g4dn.xlarge`, Azure NC-series, on-prem GPU server |
| RAM | 16 GB+ system memory |
| Disk | 30 GB+ free (models are several GB) |
| Network | **Same LAN/VPC** as SQL/gateway VM |
| Inbound | **TCP 11434 only from SQL VM private IP** — not from the internet |
| Outbound | Internet once for model download; can be blocked afterward |

**NVIDIA drivers** must be installed before bootstrap (or use a GPU-ready AMI). The bootstrap script checks `nvidia-smi` and exits with install instructions if a GPU is present but drivers are missing.

## Install flow

```text
Client IT                          Prelytical / you
─────────                          ────────────────
1. Create Linux GPU VM             (send requirements above)
2. Open firewall/SG :11434         SQL VM IP → GPU VM IP only
3. Clone gateway repo on GPU VM
4. Run bootstrap script      →     install/bootstrap-inference-linux.sh
5. Note private IP + model URL
                                   On SQL VM:
6. Skip local Ollama install       (no install_ollama_windows.ps1)
7. Run env wizard              →     configure_env_wizard.ps1 → Option 2
8. Test connectivity           →     test_ollama_connection.ps1
9. Start gateway               →     start_prelytical.ps1
```

## Step 1 — Bootstrap the GPU VM

SSH to the GPU VM as a user with `sudo`:

```bash
git clone https://github.com/Prelytical-AI/gateway.git
cd gateway
chmod +x install/bootstrap-inference-linux.sh
```

Replace `10.0.1.50` with the **SQL/gateway VM private IP**:

```bash
sudo ./install/bootstrap-inference-linux.sh \
  --allowed-ip 10.0.1.50 \
  --model qwen2.5-coder:7b
```

If the client manages firewalls outside the VM (typical on AWS/Azure), use `--skip-firewall` and configure the cloud security group instead:

```bash
sudo ./install/bootstrap-inference-linux.sh --skip-firewall
```

The script will:

- Verify NVIDIA drivers (`nvidia-smi`)
- Install Ollama
- Bind Ollama on `0.0.0.0:11434` (reachable on the private network)
- Pull the default model
- Print the `MODEL_BASE_URL` for the SQL VM

## Step 2 — Configure the SQL / gateway VM

On the **Windows** machine where Prelytical runs:

```powershell
cd C:\Projects\gateway

# Do NOT run:
#   .\install\install_ollama_windows.ps1
#   .\install\pull_default_models.ps1

.\install\configure_env_wizard.ps1
```

When prompted, choose **Option 2** (separate GPU VM) and enter the GPU private IP.

Or edit `.env` manually:

```env
MODEL_BASE_URL=http://10.0.2.47:11434/v1
MODEL_NAME=qwen2.5-coder:7b
```

## Step 3 — Verify connectivity

From the **SQL/gateway VM** (PowerShell):

```powershell
.\install\test_ollama_connection.ps1
```

This script reads `MODEL_BASE_URL` and `MODEL_NAME` from `.env`. It checks the Ollama tags endpoint, then sends a short chat request.

Expected: green **Model response** within seconds (not minutes).

### Manual checks

```powershell
# Replace with your GPU private IP
Invoke-RestMethod -Uri "http://10.0.2.47:11434/api/tags"
Test-NetConnection -ComputerName 10.0.2.47 -Port 11434
```

If these fail, the issue is almost always **network/firewall**, not Prelytical:

- Security group / NSG: allow **inbound 11434** on GPU VM **from SQL VM IP only**
- Windows firewall on SQL VM: allow **outbound** to GPU VM :11434
- Wrong IP (public vs private)
- Ollama not listening on `0.0.0.0` — re-run bootstrap or check `systemctl status ollama`

## Step 4 — Start the gateway

```powershell
.\install\test_sql_connection.ps1
.\install\start_prelytical.ps1
```

Open `http://localhost:8080` — status should show SQL connected and Model ready.

## Security notes

- **No SQL credentials** on the GPU VM — it only runs Ollama.
- **Questions, schema metadata, and query result rows** are sent to the GPU VM over the private network for SQL generation and summarization. The GPU VM remains **client-owned**.
- Restrict **11434** to the SQL VM source IP. Do not expose Ollama to the public internet.
- After models are pulled, outbound internet on the GPU VM can be disabled for tighter air-gap posture.

## Client IT checklist

```text
[ ] Linux GPU VM provisioned on same network as SQL Server
[ ] NVIDIA drivers installed (nvidia-smi works)
[ ] bootstrap-inference-linux.sh completed successfully
[ ] Firewall/SG: SQL VM → GPU VM TCP 11434 only
[ ] Private IP documented
[ ] SQL VM .env MODEL_BASE_URL points to GPU private IP
[ ] test_ollama_connection.ps1 passes from SQL VM
[ ] Gateway UI shows Model ready
[ ] Sample Ask question returns in seconds
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Connection timed out | Firewall / SG | Open 11434 from SQL VM IP only |
| Connection refused | Ollama not running | `sudo systemctl restart ollama` on GPU VM |
| Model not found | Pull failed | `ollama pull qwen2.5-coder:7b` on GPU VM |
| Slow despite GPU | CPU fallback | Fix NVIDIA drivers; confirm `nvidia-smi` in ollama process context |
| Works from GPU VM, not SQL VM | Wrong bind or SG | Bootstrap sets `OLLAMA_HOST=0.0.0.0:11434`; check SG source IP |

See also [TROUBLESHOOTING.md](TROUBLESHOOTING.md) and [ARCHITECTURE_OPTIONS.html](ARCHITECTURE_OPTIONS.html).

## Related docs

- [Same-VM POC](SAME_VM_SQLSERVER_OLLAMA_POC.md) — Option 1 (POC / demo)
- [Architecture options](ARCHITECTURE_OPTIONS.html) — compare all three deployment paths
- [Security model](SECURITY_MODEL.md) — trust boundary and guardrails
