# Troubleshooting

## ODBC driver missing

**Symptom:** `Data source name not found` or driver not listed.

**Fix:**

1. Install [ODBC Driver 18](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server) or [ODBC Driver 17](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server) (64-bit)
2. Run `Get-OdbcDriver | Where-Object {$_.Name -like "*SQL Server*"}`
3. Set `SQLSERVER_DRIVER` in `.env` to the **exact** driver name (e.g. `ODBC Driver 17 for SQL Server`)

## ODBC Driver 17 vs 18

Both drivers are supported. Use a 64-bit driver with 64-bit Python.

**Driver 17 (common on older client VMs):**

```env
SQLSERVER_DRIVER=ODBC Driver 17 for SQL Server
SQLSERVER_ENCRYPT=no
SQLSERVER_TRUST_SERVER_CERTIFICATE=true
```

**Driver 18 (default in `.env.example`):**

```env
SQLSERVER_DRIVER=ODBC Driver 18 for SQL Server
SQLSERVER_ENCRYPT=yes
SQLSERVER_TRUST_SERVER_CERTIFICATE=true
```

Passwords containing `;` or `}` are automatically escaped in the connection string.

Restart the gateway after changing `.env` (settings are cached for the process lifetime).

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

## Slow model responses / Ask never returns (CPU-only VM)

**Symptom:** Ask button shows "Working…" for many minutes, or eventually times out.

**Why:** Same-VM CPU inference is slow. Each Ask call runs Ollama locally. The first request also **loads the model into RAM** (often 3–10+ minutes on a t3.xlarge). With full dbo access, large schema metadata makes SQL generation even slower.

**Fix (try in order):**

1. **Warm the model before demo** (strongly recommended):

```powershell
.\install\warm_ollama_model.ps1
```

2. **Confirm Ollama works** (quick tags check + chat test):

```powershell
.\install\test_ollama_connection.ps1
```

3. **Use CPU-friendly `.env` defaults** (in `.env.example` — tuned for slow CPU-only VMs):

```env
MODEL_TIMEOUT_SECONDS=1800
BRIEF_TIMEOUT_SECONDS=3600
DEEP_DIVE_TIMEOUT_SECONDS=1800
MODEL_SKIP_SUMMARIZATION=true
MODEL_MAX_SCHEMA_OBJECTS=40
```

   Restart Prelytical after editing `.env`. A single chat turn on CPU can take many minutes; investigations run several model calls in sequence.

4. **Smaller model** if still too slow:

```powershell
ollama pull qwen2.5-coder:3b
```

   Set `MODEL_NAME=qwen2.5-coder:3b` in `.env`.

5. **Check the Audit Log tab** — if you see `model_sql_generated` but no `sql_executed`, SQL generation finished and the hang is elsewhere. If only `question_received`, Ollama is still generating SQL.

6. **Production path:** GPU inference VM — see [GPU_INFERENCE_VM.md](GPU_INFERENCE_VM.md).

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
