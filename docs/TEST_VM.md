# Gateway AWS test VM

Use this VM to practice a **fresh gateway install** against a real SQL Server instance with seeded data.

## Connection

After `./infra/deploy-test-vm.sh` completes:

| Item | Value |
|------|-------|
| RDP host | Stack output `PublicIp` (`52.90.192.205` for current test stack) |
| RDP user | `Administrator` |
| RDP password | See **Option A** or **Option B** below |
| SQL host | `localhost` |
| SQL database | `PrelyticalDemoDW` |
| SQL login | `prelytical_readonly` |
| SQL password | `PrelyticalTest!2026` (or your `READONLY_PASSWORD`) |

### Option A — Known admin password (no `.pem` file needed)

If you do not have the EC2 private key locally, reset the Administrator password via SSM:

```bash
aws ssm send-command \
  --region us-east-1 \
  --instance-ids i-084acc964f3517aad \
  --document-name AWS-RunPowerShellScript \
  --parameters 'commands=["net user Administrator '\''YourPasswordHere'\''","net user Administrator /active:yes"]'
```

For the current test VM, a temporary password was set: **`PrelyticalAdmin!2026`**

### Option B — Decrypt the launch password (requires `.pem`)

`get-password-data` only works if you have the **private key file** used when the key pair was created. It is not stored in AWS.

```bash
aws ec2 get-password-data \
  --instance-id i-084acc964f3517aad \
  --priv-launch-key /full/path/to/Dev-Mac.pem \
  --region us-east-1
```

The instance was launched with key pair **`Dev-Mac`**. If `~/.ssh/Dev-Mac.pem` does not exist, use Option A or locate the key from the machine where `Dev-Mac` was originally created (often AWS Console → download at key creation time).

**Common error:** `priv-launch-key should be a path to the local SSH private key file` — the file path is wrong or missing.

On the VM, bootstrap notes are at `C:\PrelyticalBootstrap\README.txt`.

## Test data

**Tables**

- `dbo.Regions` — Midwest, West, East, South
- `dbo.ProductCategories` — Analytics Platform, Data Integration, Reporting, Support Services
- `dbo.Customers` — 8 customers across segments (Enterprise, Mid-Market, SMB)
- `dbo.Orders` — 15 orders (Jan–Jun 2025), mix of Closed and Open

**Views**

- `ai.vw_sales_by_region`
- `ai.vw_sales_by_category`
- `ai.vw_monthly_revenue`

## Sample analysis questions

```text
Which region has the highest total revenue?
What are the top 3 customers by order revenue?
Show monthly revenue by product category.
How many open orders are there by region?
Which enterprise customers have the highest annual contract value?
Compare Analytics Platform revenue vs Reporting.
```

## Fresh install checklist

The VM intentionally does **not** install Ollama or Prelytical — that's your test.

```powershell
cd C:\Projects
git clone https://github.com/Prelytical-AI/gateway.git
cd gateway

.\install\check_vm_readiness.ps1
.\install\install_ollama_windows.ps1
.\install\pull_default_models.ps1
.\install\configure_env_wizard.ps1
```

SQL scripts **already applied by bootstrap** (skip re-running unless testing):

- Database + seed data (`05_seed_test_warehouse.sql`)
- Read-only login + dbo/ai SELECT grants

You may still run `sql\03_permission_check.sql` to verify.

```powershell
.\install\test_sql_connection.ps1
.\install\test_ollama_connection.ps1
.\install\start_prelytical.ps1
```

Open `http://localhost:8080`.

## Tear down

```bash
aws cloudformation delete-stack --stack-name prelytical-gateway-test --region us-east-1
```
