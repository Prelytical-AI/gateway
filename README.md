# Prelytical Secure SQL Gateway

A same-VM POC for running AI against sensitive SQL Server data using:

- SQL Server read-only access
- Approved `ai`-safe views
- Local Ollama model runtime
- App-level SQL guardrails
- Local audit logging
- Browser UI at `http://localhost:8080`

This gateway lives in the `gateway/` folder alongside the cloud Prelytical platform (`../platform/`) and public marketing site (`../public-site/`). It is a **self-contained on-premises deployment** for environments where data cannot leave the VM.

## Test Today (Windows VM)

Open PowerShell as Administrator:

```powershell
cd C:\Projects\prelytical\gateway

.\install\check_vm_readiness.ps1
.\install\install_ollama_windows.ps1
.\install\pull_default_models.ps1
.\install\configure_env_wizard.ps1
```

Run SQL scripts in SSMS (`sql\00` through `sql\03`), then:

```powershell
.\install\test_ollama_connection.ps1
.\install\test_sql_connection.ps1
.\install\start_prelytical.ps1
```

Open **http://localhost:8080**

## Project layout

```text
prelytical/
  gateway/
    app/           FastAPI backend + static UI
    install/       Windows PowerShell setup scripts
    sql/           SQL Server schema, login, demo views
    docs/          POC guide, security model, troubleshooting
    tests/         Guardrail and prompt unit tests
```

## API endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | App, SQL, and model status |
| GET | `/api/config/safe` | Non-sensitive configuration |
| GET | `/api/schema` | Allowed schema metadata |
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

On macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest tests
python run_local.py
```

## Documentation

- [Same-VM POC guide](docs/SAME_VM_SQLSERVER_OLLAMA_POC.md)
- [Client demo script](docs/CLIENT_TEST_SCRIPT.md)
- [Security model](docs/SECURITY_MODEL.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)

## Acceptance criteria

On a Windows SQL Server VM you should be able to:

1. Run readiness check and install Ollama
2. Configure `.env` and SQL scripts
3. Start Prelytical on port 8080
4. Ask safe business questions against `ai` views
5. See generated SQL, results, and summaries
6. Have unsafe requests blocked with audit trail
