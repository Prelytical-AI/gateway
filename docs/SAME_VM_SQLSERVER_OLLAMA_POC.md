# Same-VM SQL Server + Ollama POC

Install **Prelytical Secure SQL Gateway** on a Windows VM that already has SQL Server (replicated dev DB, etc.).

## What you get

- Browser UI at `http://localhost:8080` (localhost only)
- Read-only SQL Server access — **no CUD** even if the model hallucinates bad SQL
- **Ollama on the same VM** at `localhost:11434` for SQL generation and summarization (local model, not cloud AI)
- SELECT-only guardrails and local SQLite audit logging
- No Docker or Kubernetes required

## Security assumption

**The VM is secure.** Data exposure on the VM (query results in the UI, schema/rows in Ollama’s local context) is acceptable. The goal is to prevent **writes** and **off-box AI**, not to hide data from processes on the same machine.

Still enforced:

- Read-only SQL login
- Guardrails: SELECT only, no DROP/DELETE/EXEC/etc.
- `TOP 200` row cap by default

## Prerequisites

- Windows VM with admin rights
- SQL Server installed locally
- Python 3.11+
- ODBC Driver 17 or 18 for SQL Server
- Internet only needed once (Ollama install + `ollama pull`); inference runs offline after that

## Install flow

Open **PowerShell as Administrator**:

```powershell
cd C:\Projects
git clone https://github.com/Prelytical-AI/gateway.git
cd gateway

.\install\check_vm_readiness.ps1
.\install\install_ollama_windows.ps1
.\install\pull_default_models.ps1
.\install\configure_env_wizard.ps1
```

### SQL scripts (SSMS)

Edit database name and password in the scripts, then run against your database:

#### Typical install (real client database, full dbo read)

1. `sql\00_create_ai_schema.sql`
2. `sql\01_create_readonly_login.sql` — edit password first
3. **`sql\02_grant_dbo_readonly.sql`** — grants SELECT on all `dbo` tables/views
4. `sql\03_permission_check.sql` — adjust table/view name if not using demo data

**Skip** `sql\02_create_sample_ai_views.sql` unless you need the built-in demo dataset.

#### Demo install (no client tables yet)

Run `02_create_sample_ai_views.sql` instead of (or in addition to) `02_grant_dbo_readonly.sql` for fake sales data and `ai.vw_demo_sales_summary`.

### `.env` for open dbo access

Confirm after the wizard (or edit `.env` manually):

```env
SQLSERVER_DATABASE=YourDatabaseName
SQLSERVER_ALLOWED_SCHEMAS=ai,dbo
SQLSERVER_BLOCKED_SCHEMAS=sys,INFORMATION_SCHEMA
GUARDRAILS_BLOCK_PII_COLUMNS=false
```

Match `SQLSERVER_PASSWORD` to the login created in step 01.

### Verify and start

```powershell
.\install\test_ollama_connection.ps1
.\install\test_sql_connection.ps1
.\install\start_prelytical.ps1
```

Open `http://localhost:8080`.

## How the local model fits in

```text
You ask a question in the browser
    → Prelytical sends schema + question to Ollama (127.0.0.1:11434)
    → Ollama returns a SELECT statement
    → Guardrails validate it
    → Prelytical runs it against SQL Server (read-only)
    → Result rows go back to Ollama for a plain-English summary
    → You see SQL + table + answer in the UI
```

All of that stays on the VM. Ollama is the **local model server**, like nginx for web — not an external API.

## Test questions

```text
What tables are in dbo?
Show me the top 10 rows from [YourTable].
Which region has the highest revenue?
```

## Blocked tests (should still fail)

```text
Delete all sales rows.
Drop the customer table.
Run xp_cmdshell.
```

With open dbo access, `SELECT * FROM dbo.Customers` is **allowed**. Writes and admin SQL are not.

Paste examples from `sql\04_guardrail_test_queries.sql` into the **SQL Validator** tab (some are blocked, some allowed depending on your schema config).

## Curated views (optional)

Use `ai` views when you want a narrower surface later:

```sql
CREATE OR ALTER VIEW ai.vw_orders AS SELECT * FROM dbo.Orders;
```

Then restrict `.env` to `SQLSERVER_ALLOWED_SCHEMAS=ai` only. Not required on a trusted VM with full dbo grant.

## Optional Windows service

```powershell
.\install\install_windows_service.ps1
```

Requires NSSM. For testing, `start_prelytical.ps1` in a terminal is enough.

## Related docs

- `CLIENT_TEST_SCRIPT.md` — 10-minute demo
- `SECURITY_MODEL.md` — layers and hardening options
- `TROUBLESHOOTING.md` — ODBC, SQL login, Ollama, ports
