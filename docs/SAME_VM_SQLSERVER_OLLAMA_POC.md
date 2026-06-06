# Same-VM SQL Server + Ollama POC

This guide walks through installing and testing **Prelytical Secure SQL Gateway** on a Windows VM that already has SQL Server (with a replicated or dev database).

## What you get

- Local browser UI at `http://localhost:8080`
- Read-only SQL Server access through approved `ai` schema views
- Local Ollama model for SQL generation and summarization
- App-level SQL guardrails and local SQLite audit logging
- No Docker, cloud AI, or external dependencies required for the POC

## Prerequisites

- Windows VM with admin rights
- SQL Server installed locally
- Python 3.11+
- ODBC Driver 17 or 18 for SQL Server
- Internet optional (needed to install Ollama/models; app degrades gracefully if Ollama is offline)

## Install flow (run today)

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

Run these SQL scripts in **SQL Server Management Studio (SSMS)** against your target database:

1. `sql\00_create_ai_schema.sql`
2. `sql\01_create_readonly_login.sql` (edit password first)
3. `sql\02_create_sample_ai_views.sql` (demo data + `ai.vw_demo_sales_summary`)
4. `sql\03_permission_check.sql`

Then verify connections and start the app:

```powershell
.\install\test_ollama_connection.ps1
.\install\test_sql_connection.ps1
.\install\start_prelytical.ps1
```

Open:

```text
http://localhost:8080
```

## Safe test questions

```text
What AI-safe views are available?
Summarize the demo sales data by month and region.
Which region has the highest revenue?
Show me the top product categories by revenue.
```

## Blocked tests (should fail guardrails)

```text
Delete all sales rows.
Show me SSNs.
Drop the customer table.
Query dbo.Customers directly.
Run xp_cmdshell.
```

Paste SQL from `sql\04_guardrail_test_queries.sql` into the **SQL Validator** tab for quick checks.

## Client-specific rollout

Replace the demo section in `sql\02_create_sample_ai_views.sql` with real `ai` views that:

- Aggregate or mask sensitive fields
- Expose only business-approved columns
- Never grant `dbo` access to the read-only login

## Optional Windows service

```powershell
.\install\install_windows_service.ps1
```

NSSM is optional. For today's test, running `start_prelytical.ps1` in a terminal is enough.

## Related docs

- `CLIENT_TEST_SCRIPT.md` — 10-minute demo script
- `SECURITY_MODEL.md` — security boundaries
- `TROUBLESHOOTING.md` — common fixes
