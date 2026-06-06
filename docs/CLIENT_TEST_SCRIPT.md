# Client Test Script (10 minutes)

Use this script to demo Prelytical Secure SQL Gateway on the SQL Server VM.

## Before the demo (5 minutes)

1. Confirm Prelytical is running: `http://localhost:8080`
2. Confirm status cards show SQL Server connected and Model ready
3. Open SSMS in background if you want to show the `ai` schema exists

## Demo flow

### 1. Show app running on the SQL Server VM (1 min)

- Open browser to `http://localhost:8080`
- Point out: everything runs on this VM — SQL Server, Ollama, Prelytical

### 2. Show configuration (1 min)

- Status cards: localhost SQL Server, localhost Ollama
- Allowed schema = `ai`
- Max rows cap visible

### 3. Load schema (1 min)

- Open **Schema** tab → **Load Schema**
- Show `ai.vw_demo_sales_summary` and its columns
- Explain client views replace demo views in production

### 4. Ask a safe business question (2 min)

Question:

```text
Which region has the highest revenue?
```

- Click **Ask Prelytical**
- Show generated SQL (SELECT only, `ai` schema, TOP limit)
- Show validation passed
- Show summarized business answer and result table

### 5. Ask another safe question (1 min)

```text
Show me the top product categories by revenue.
```

- Highlight aggregated query style

### 6. Ask an unsafe question (1 min)

```text
Delete all sales rows.
```

or

```text
Show me SSNs from customer data.
```

- Show blocked response
- Show guardrail reason (not SELECT / sensitive column / etc.)

### 7. SQL Validator quick check (1 min)

Paste from `sql/04_guardrail_test_queries.sql`:

```sql
SELECT * FROM dbo.Customers;
```

- Validate → blocked (dbo schema not allowed)

### 8. Audit log (1 min)

- Open **Audit Log** tab
- Load recent events
- Show question received, SQL generated, validation, execution, summary events
- Note: full result sets are not stored in audit by default

### 9. Close with security story (1 min)

- Read-only SQL login
- `ai` schema only at DB layer
- App guardrails as second layer
- Local Ollama — no data sent to hosted AI
- Local audit trail on the VM

## Talking points

- "We decide what's safe to analyze before exposing row-level data."
- "Executives get answers; analysts get reusable SQL and audit history."
- "If internet is restricted, SQL guardrails and read-only access still apply."
