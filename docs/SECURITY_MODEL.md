# Security Model

Prelytical Secure SQL Gateway is designed for sensitive data environments where AI must stay on-premises.

## Deployment boundary

- **Same-VM deployment**: SQL Server, Ollama, and Prelytical run on one Windows VM
- **Local browser UI**: `http://localhost:8080` (binds to loopback by default)
- **No hosted AI required**: prompts go to local Ollama only

## Data access layers

### 1. SQL Server least privilege

- Dedicated login: `prelytical_readonly`
- **SELECT only** on schema `ai`
- Explicit **DENY** on INSERT, UPDATE, DELETE, ALTER, CONTROL
- No sysadmin or dbo access for the application

### 2. Approved views only

- Application reads metadata and executes queries only against allowed schemas (default: `ai`)
- Client teams publish curated views — aggregated, masked, or de-identified
- Raw `dbo` tables are blocked by default at app and DB layers

### 3. App-level guardrails

Before any SQL executes, the gateway validates:

- Single SELECT (or WITH … SELECT) statement only
- No DDL/DML/admin commands (DROP, DELETE, EXEC, xp_cmdshell, etc.)
- No cross-database references
- No blocked schemas (`dbo`, `sys`, etc.)
- Optional PII column pattern blocking (ssn, email, phone, etc.)
- Automatic TOP row cap when missing

Unsafe SQL is blocked **before** reaching SQL Server.

### 4. Model behavior constraints

Prompt contract instructs the model to:

- Generate one read-only SELECT
- Use only provided schema metadata
- Prefer aggregates over raw detail
- Never claim row-level analysis beyond returned results

## Audit and logging

- Local SQLite audit database (`prelytical_audit.sqlite3`)
- Events: questions, generated SQL, validation outcome, row counts, errors
- **Full result sets are not stored** in audit by default
- SQL passwords are never logged

## Privacy posture

- Default path avoids raw PII columns via pattern guardrails
- Production rollout should use `ai` views that exclude or aggregate sensitive fields
- Summaries are grounded in query results only (no invented numbers)

## What this POC is not

- Not a replacement for database firewall / network segmentation
- Not a substitute for view design and data governance by the client
- Not multi-tenant SaaS (see [`../platform/`](../platform/) for the cloud product)

## Hardening checklist for production

- [ ] Replace demo views with client-approved `ai` views
- [ ] Rotate read-only password; store in secure secret store
- [ ] Restrict VM RDP/access; run Prelytical as dedicated service account
- [ ] Enable SQL Server auditing for the read-only login
- [ ] Review guardrail PII patterns for client data dictionary
- [ ] Set up audit DB backup and retention policy
