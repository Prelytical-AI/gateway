# Gateway test VM (AWS)

Provision a Windows Server 2022 + SQL Server 2022 Express EC2 instance seeded with `PrelyticalDemoDW` test data for fresh gateway install testing.

## What it creates

- EC2 `t3.xlarge` Windows instance (default)
- SQL Server 2022 Express (default instance, TCP 1433)
- Database `PrelyticalDemoDW` with:
  - `dbo.Regions`, `dbo.ProductCategories`, `dbo.Customers`, `dbo.Orders`
  - `ai.vw_sales_by_region`, `ai.vw_sales_by_category`, `ai.vw_monthly_revenue`
- Read-only login `prelytical_readonly`
- Git pre-installed (gateway/Ollama install is left to you)

## Deploy

Requires AWS CLI credentials with EC2, CloudFormation, SSM, and S3 permissions.

```bash
cd gateway/infra
chmod +x deploy-test-vm.sh

# Optional overrides
export KEY_PAIR_NAME=Dev-Mac
export AWS_REGION=us-east-1
export ALLOWED_RDP_CIDR="$(curl -s https://checkip.amazonaws.com)/32"

./deploy-test-vm.sh
```

Default read-only SQL password: `PrelyticalTest!2026` (override with `READONLY_PASSWORD`).

## After deploy

1. RDP to the public IP (decrypt Administrator password with your EC2 key pair)
2. Confirm `C:\PrelyticalBootstrap\README.txt` exists
3. Run a fresh gateway install:

```powershell
git clone https://github.com/Prelytical-AI/gateway.git C:\Projects\gateway
cd C:\Projects\gateway
.\install\check_vm_readiness.ps1
```

Use these values in the env wizard:

```text
SQL host:     localhost
Database:     PrelyticalDemoDW
Username:     prelytical_readonly
Password:     PrelyticalTest!2026
```

## Tear down

```bash
aws cloudformation delete-stack --stack-name prelytical-gateway-test --region us-east-1
```

Empty and delete the bootstrap S3 bucket if CloudFormation retention blocks deletion.

## Notes

- Deploy uses the **currently configured AWS CLI account** (`aws sts get-caller-identity`).
- Platform production infra uses account `169970911838`; use a profile with access to that account if required.
- Restrict `ALLOWED_RDP_CIDR` to your IP — default `0.0.0.0/0` is for quick testing only.

See also [TEST_VM.md](../docs/TEST_VM.md).
