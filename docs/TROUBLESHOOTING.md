# Troubleshooting

## ODBC driver missing

**Symptom:** `Data source name not found` or driver not listed.

**Fix:**

1. Install [Microsoft ODBC Driver 18 for SQL Server](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server)
2. Run `Get-OdbcDriver | Where-Object {$_.Name -like "*SQL Server*"}`
3. Update `SQLSERVER_DRIVER` in `.env` to match installed driver name

## SQL login failed

**Symptom:** `Login failed for user 'prelytical_readonly'`.

**Fix:**

1. Re-run `sql/01_create_readonly_login.sql` with correct password
2. Ensure SQL Server authentication (mixed mode) is enabled if using SQL login
3. Match password in `.env` from `configure_env_wizard.ps1`

## SQL Server not listening on TCP/IP

**Symptom:** Connection timeout to `localhost,1433`.

**Fix:**

1. Open **SQL Server Configuration Manager**
2. Enable **TCP/IP** for your instance
3. Restart SQL Server service
4. Confirm port 1433 (or update `SQLSERVER_PORT`)

## Named instance connection

**Symptom:** Cannot connect to `SQLEXPRESS` or other named instance.

**Fix:**

Set in `.env`:

```env
SQLSERVER_HOST=localhost
SQLSERVER_INSTANCE=SQLEXPRESS
SQLSERVER_PORT=1433
```

Or use dynamic port from SQL Configuration Manager if non-default.

## Ollama not running

**Symptom:** `Cannot connect to Ollama` on health check or Ask.

**Fix:**

1. Start Ollama from Start menu or run `ollama serve`
2. Verify: `Test-NetConnection localhost -Port 11434`
3. Run `.\install\test_ollama_connection.ps1`

## Model not pulled

**Symptom:** Model API error 404 or model not found.

**Fix:**

```powershell
ollama pull qwen2.5-coder:7b
```

Update `MODEL_NAME` in `.env` if using a different model.

## Port 8080 in use

**Symptom:** Uvicorn fails to bind port 8080.

**Fix:**

1. Find process: `Get-NetTCPConnection -LocalPort 8080`
2. Stop conflicting app or set `APP_PORT=8081` in `.env`

## Docker not needed

This POC does **not** require Docker. Use native Python + local SQL Server + local Ollama.

## Slow model responses on CPU-only VM

**Symptom:** Ask flow takes 30–120+ seconds.

**Fix:**

- Use a smaller model (e.g. `qwen2.5-coder:3b` if available)
- Increase `MODEL_TIMEOUT_SECONDS` in `.env`
- Expect slower summarization step after SQL executes

## Schema tab empty

**Symptom:** No objects under `ai` schema.

**Fix:**

1. Run `sql/00_create_ai_schema.sql` and `sql/02_create_sample_ai_views.sql`
2. Confirm login has `SELECT` on schema `ai`
3. Run `sql/03_permission_check.sql`

## Guardrails block valid query

**Symptom:** Safe-looking SELECT blocked.

**Fix:**

1. Use schema-qualified names: `ai.vw_demo_sales_summary`
2. Avoid CTEs without TOP in final SELECT
3. Check PII column names against `GUARDRAILS_BLOCKED_COLUMN_PATTERNS`
4. Use **SQL Validator** tab to see exact `blocked_reason`

## pyodbc / Python issues on Mac/Linux dev machines

This POC targets **Windows + SQL Server**. Development on macOS can run unit tests (`pytest`) but not full SQL Server integration without a remote SQL instance.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest tests
```
