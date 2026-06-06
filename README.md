# Prelytical Secure SQL Gateway

On-premises Prelytical for sensitive SQL Server environments:

- **Executive briefs** — schema-first readiness, data shape, ranked opportunities, standalone HTML report
- **Read-only SQL analytics** — natural language → SELECT → results (follow-on deep dives)
- **Ollama** on the same VM or a private GPU inference box (not cloud AI)
- Local audit logging · Browser UI at `http://localhost:8080`

The cloud product lives in [`../platform/`](../platform/). This gateway delivers the same **brief generation contract** using live SQL Server schema metadata as source context.

This is a **standalone repository** for on-premises installs. It also appears as the `gateway/` submodule inside the [Prelytical workspace](https://github.com/Prelytical-AI/prelytical).

## Security model (default assumption)

**The VM is the trust boundary.** Query results and schema metadata are sent to Ollama on the same machine for SQL generation and summarization. That stays on-box — nothing goes to hosted AI after setup.

What is still enforced:

- **No writes** — read-only SQL login + guardrails block CUD/DDL/admin SQL
- **Row cap** — `TOP 200` appended when missing (configurable)
- **Audit trail** — questions, SQL, validation, row counts logged locally

What you control:

- **Which schemas/tables** the login can read (`ai` only, `dbo`, or both)
- **PII column blocking** in guardrails (off by default in `.env.example` for trusted VMs)

## Architecture

```text
Browser → localhost:8080 (Prelytical / FastAPI)
              ↓                    ↓
      localhost SQL Server    localhost:11434 (Ollama)
      read-only SELECT        qwen2.5-coder:7b on disk/GPU
```

Ollama is not a cloud service here — it is the **local inference process** on the VM.

## Install (Windows VM)

Open PowerShell as Administrator:

```powershell
cd C:\Projects
git clone https://github.com/Prelytical-AI/gateway.git
cd gateway

.\install\check_vm_readiness.ps1
.\install\install_ollama_windows.ps1
.\install\pull_default_models.ps1
.\install\configure_env_wizard.ps1
```

### SQL setup in SSMS

Run against your target database (edit names/passwords in the scripts first):

| Step | Script | When |
|------|--------|------|
| 1 | `sql\00_create_ai_schema.sql` | Optional but recommended |
| 2 | `sql\01_create_readonly_login.sql` | Always — creates `prelytical_readonly` |
| 3a | **`sql\02_grant_dbo_readonly.sql`** | **Typical — full read access to `dbo` tables** |
| 3b | `sql\02_create_sample_ai_views.sql` | **Demo only** — fake data when no client DB exists |
| 4 | `sql\03_permission_check.sql` | Always — verify login can read |

**Most installs:** run `00`, `01`, **`02_grant_dbo_readonly.sql`**, `03`. Skip `02_create_sample_ai_views.sql` if you already have a real database.

### Open access `.env` (typical)

After the wizard, confirm these values in `.env` (or set manually):

```env
SQLSERVER_ALLOWED_SCHEMAS=ai,dbo
SQLSERVER_BLOCKED_SCHEMAS=sys,INFORMATION_SCHEMA
GUARDRAILS_BLOCK_PII_COLUMNS=false
```

Use your real database name and the same password as in `01_create_readonly_login.sql`.

### Start and verify

```powershell
.\install\test_ollama_connection.ps1
.\install\test_sql_connection.ps1
.\install\start_prelytical.ps1
```

Open **http://localhost:8080** — status cards should show SQL and Model connected.

### Export briefs off the VM

Set an auto-export folder in `.env` (created if missing). Each generated brief is saved as a timestamped `.html` file:

```env
BRIEF_EXPORT_PATH=C:\PrelyticalExports\briefs
```

UNC share example:

```env
BRIEF_EXPORT_PATH=\\fileserver\reports\prelytical
```

The UI shows the saved path after generation. Download HTML still works for ad-hoc copies.

## Production: GPU inference VM (Option 2)

For faster responses, run Ollama on a **separate Linux GPU VM** on the same private network. The gateway stays on the SQL Server VM; only `MODEL_BASE_URL` changes.

1. Client IT provisions a Linux GPU VM (see [GPU inference VM guide](docs/GPU_INFERENCE_VM.md))
2. On the GPU VM: `sudo ./install/bootstrap-inference-linux.sh --allowed-ip <sql-vm-private-ip>`
3. On the SQL VM: skip `install_ollama_windows.ps1`, run `configure_env_wizard.ps1` → Option 2
4. Verify: `.\install\test_ollama_connection.ps1`

See [Architecture options](docs/ARCHITECTURE_OPTIONS.html) for a comparison of all deployment paths.

### Test questions

```text
What tables are available in dbo?
Which region has the highest revenue?
Summarize sales by month.
```

**Should still block** (no writes/admin):

```text
Delete all rows from Orders.
Drop the Customers table.
Run xp_cmdshell.
```

## Alternative: curated `ai` views only

If you want a narrower read surface later (not required on a trusted VM):

- Grant only `ai` in `01_create_readonly_login.sql`
- Create views: `CREATE VIEW ai.vw_x AS SELECT … FROM dbo.x`
- Set `SQLSERVER_ALLOWED_SCHEMAS=ai` and add `dbo` to blocked schemas

See [Security model](docs/SECURITY_MODEL.md).

## Project layout

```text
gateway/
  app/           FastAPI backend + static UI
  install/       Windows PowerShell setup scripts
  sql/           SQL Server login, dbo grant, optional demo views
  docs/          POC guide, security model, troubleshooting
  tests/         Guardrail and prompt unit tests
```

**Repository:** https://github.com/Prelytical-AI/gateway

## API endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | App, SQL, and model status |
| GET | `/api/config/safe` | Non-sensitive configuration |
| GET | `/api/schema` | Allowed schema metadata |
| POST | `/api/brief/generate` | Executive brief + HTML report from schema metadata |
| POST | `/api/ask` | Natural language → SQL → results → summary |
| POST | `/api/sql/validate` | Validate SQL without executing |
| POST | `/api/sql/execute` | Validate and execute read-only SQL |
| GET | `/api/audit/recent` | Recent audit events |

## Local development (unit tests)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\pip.exe install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest tests
```

## Documentation

- [GPU inference VM](docs/GPU_INFERENCE_VM.md) — Option 2: separate Linux GPU box + bootstrap script
- [Architecture options](docs/ARCHITECTURE_OPTIONS.html) — same-VM vs split-VM vs cloud inference
- [AWS test VM](docs/TEST_VM.md) — provision a Windows SQL Server EC2 for fresh install testing
- [Same-VM POC guide](docs/SAME_VM_SQLSERVER_OLLAMA_POC.md) — full walkthrough
- [Client demo script](docs/CLIENT_TEST_SCRIPT.md)
- [Security model](docs/SECURITY_MODEL.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
