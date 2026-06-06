#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INFRA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

STACK_NAME="${STACK_NAME:-prelytical-gateway-test}"
REGION="${AWS_REGION:-us-east-1}"
KEY_PAIR_NAME="${KEY_PAIR_NAME:-Dev-Mac}"
INSTANCE_TYPE="${INSTANCE_TYPE:-t3.xlarge}"
ALLOWED_RDP_CIDR="${ALLOWED_RDP_CIDR:-0.0.0.0/0}"
READONLY_PASSWORD="${READONLY_PASSWORD:-PrelyticalTest!2026}"

echo "=== Prelytical gateway test VM deploy ==="
echo "Stack:   $STACK_NAME"
echo "Region:  $REGION"
echo "KeyPair: $KEY_PAIR_NAME"

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
echo "Account: $ACCOUNT_ID"

VPC_ID="$(aws ec2 describe-vpcs --region "$REGION" --filters Name=isDefault,Values=true --query 'Vpcs[0].VpcId' --output text)"
SUBNET_ID="$(aws ec2 describe-subnets --region "$REGION" --filters Name=vpc-id,Values="$VPC_ID" Name=default-for-az,Values=true --query 'Subnets[0].SubnetId' --output text)"
echo "VPC:     $VPC_ID"
echo "Subnet:  $SUBNET_ID"

if aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" >/dev/null 2>&1; then
  echo "Updating existing stack..."
  if ! aws cloudformation update-stack \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --capabilities CAPABILITY_NAMED_IAM \
    --template-body "file://${INFRA_DIR}/test-vm.yaml" \
    --parameters \
      "ParameterKey=KeyPairName,ParameterValue=${KEY_PAIR_NAME}" \
      "ParameterKey=InstanceType,ParameterValue=${INSTANCE_TYPE}" \
      "ParameterKey=AllowedRdpCidr,ParameterValue=${ALLOWED_RDP_CIDR}" \
      "ParameterKey=ReadOnlyPassword,ParameterValue=${READONLY_PASSWORD}" \
      "ParameterKey=VpcId,ParameterValue=${VPC_ID}" \
      "ParameterKey=SubnetId,ParameterValue=${SUBNET_ID}" 2>&1; then
    echo "No stack updates required or update already in progress."
  fi
  aws cloudformation wait stack-update-complete --stack-name "$STACK_NAME" --region "$REGION" || true
else
  echo "Creating stack..."
  aws cloudformation create-stack \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --capabilities CAPABILITY_NAMED_IAM \
    --template-body "file://${INFRA_DIR}/test-vm.yaml" \
    --parameters \
      "ParameterKey=KeyPairName,ParameterValue=${KEY_PAIR_NAME}" \
      "ParameterKey=InstanceType,ParameterValue=${INSTANCE_TYPE}" \
      "ParameterKey=AllowedRdpCidr,ParameterValue=${ALLOWED_RDP_CIDR}" \
      "ParameterKey=ReadOnlyPassword,ParameterValue=${READONLY_PASSWORD}" \
      "ParameterKey=VpcId,ParameterValue=${VPC_ID}" \
      "ParameterKey=SubnetId,ParameterValue=${SUBNET_ID}"
  aws cloudformation wait stack-create-complete --stack-name "$STACK_NAME" --region "$REGION"
fi

INSTANCE_ID="$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='InstanceId'].OutputValue" --output text)"
BUCKET="$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='BootstrapBucketName'].OutputValue" --output text)"
PUBLIC_IP="$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='PublicIp'].OutputValue" --output text)"
SSM_PARAM="$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='ReadOnlyPasswordParameterName'].OutputValue" --output text)"

echo "Uploading bootstrap assets to s3://${BUCKET}/"
aws s3 cp "${ROOT_DIR}/sql/05_seed_test_warehouse.sql" "s3://${BUCKET}/05_seed_test_warehouse.sql" --region "$REGION"
aws s3 cp "${INFRA_DIR}/scripts/bootstrap-test-vm.ps1" "s3://${BUCKET}/bootstrap-test-vm.ps1" --region "$REGION"

SEED_URL="$(aws s3 presign "s3://${BUCKET}/05_seed_test_warehouse.sql" --expires-in 7200 --region "$REGION")"
BOOTSTRAP_URL="$(aws s3 presign "s3://${BUCKET}/bootstrap-test-vm.ps1" --expires-in 7200 --region "$REGION")"

echo "Waiting for SSM agent on ${INSTANCE_ID}..."
PING=""
for _ in $(seq 1 60); do
  PING="$(aws ssm describe-instance-information --region "$REGION" \
    --filters "Key=InstanceIds,Values=${INSTANCE_ID}" \
    --query "InstanceInformationList[0].PingStatus" --output text 2>/dev/null || true)"
  if [[ "$PING" == "Online" ]]; then
    break
  fi
  sleep 20
done

if [[ "$PING" != "Online" ]]; then
  echo "SSM agent not online yet. Bootstrap manually later with docs/TEST_VM.md"
  exit 1
fi

COMMAND_FILE="$(mktemp)"
export SEED_URL BOOTSTRAP_URL READONLY_PASSWORD INSTANCE_ID COMMAND_FILE
python3 <<'PY'
import json
import os

seed_url = os.environ["SEED_URL"]
bootstrap_url = os.environ["BOOTSTRAP_URL"]
password = os.environ["READONLY_PASSWORD"]
instance_id = os.environ["INSTANCE_ID"]
command_file = os.environ["COMMAND_FILE"]

commands = [
    "New-Item -ItemType Directory -Force -Path C:\\PrelyticalBootstrap | Out-Null",
    f"Invoke-WebRequest -Uri '{seed_url}' -OutFile C:\\PrelyticalBootstrap\\05_seed_test_warehouse.sql",
    f"Invoke-WebRequest -Uri '{bootstrap_url}' -OutFile C:\\PrelyticalBootstrap\\bootstrap-test-vm.ps1",
    f"powershell.exe -ExecutionPolicy Bypass -File C:\\PrelyticalBootstrap\\bootstrap-test-vm.ps1 -ReadOnlyPassword '{password}'",
]
payload = {
    "DocumentName": "AWS-RunPowerShellScript",
    "Comment": "Prelytical gateway test VM bootstrap",
    "InstanceIds": [instance_id],
    "Parameters": {"commands": commands},
}
with open(command_file, "w", encoding="utf-8") as f:
    json.dump(payload, f)
PY

COMMAND_ID="$(aws ssm send-command --region "$REGION" --cli-input-json "file://${COMMAND_FILE}" --query Command.CommandId --output text)"
rm -f "$COMMAND_FILE"

echo "Bootstrap command: $COMMAND_ID"
aws ssm wait command-executed --command-id "$COMMAND_ID" --instance-id "$INSTANCE_ID" --region "$REGION"

STATUS="$(aws ssm get-command-invocation --command-id "$COMMAND_ID" --instance-id "$INSTANCE_ID" --region "$REGION" --query Status --output text)"
if [[ "$STATUS" != "Success" ]]; then
  echo "Bootstrap failed with status: $STATUS"
  aws ssm get-command-invocation --command-id "$COMMAND_ID" --instance-id "$INSTANCE_ID" --region "$REGION" --query StandardErrorContent --output text || true
  aws ssm get-command-invocation --command-id "$COMMAND_ID" --instance-id "$INSTANCE_ID" --region "$REGION" --query StandardOutputContent --output text || true
  exit 1
fi

cat <<EOF

=== Prelytical gateway test VM ready ===

AWS account:  ${ACCOUNT_ID}
Region:       ${REGION}
Instance:     ${INSTANCE_ID}
Public IP:    ${PUBLIC_IP}

RDP:
  Host: ${PUBLIC_IP}
  User: Administrator
  Password:
    aws ec2 get-password-data --instance-id ${INSTANCE_ID} --priv-launch-key /path/to/${KEY_PAIR_NAME}.pem --region ${REGION}

SQL (gateway .env wizard):
  Host:     localhost
  Database: PrelyticalDemoDW
  Login:    prelytical_readonly
  Password: ${READONLY_PASSWORD}
  SSM:      ${SSM_PARAM}

VM notes: C:\\PrelyticalBootstrap\\README.txt

Fresh install:
  git clone https://github.com/Prelytical-AI/gateway.git C:\\Projects\\gateway
  cd C:\\Projects\\gateway
  .\\install\\check_vm_readiness.ps1

EOF
