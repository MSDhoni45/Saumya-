#!/usr/bin/env bash
# Bootstrap script for first-time ECS setup or manual re-deploy.
# For day-to-day deploys the GitHub Actions workflow handles this automatically.
#
# Prerequisites:
#   aws cli v2 configured with appropriate permissions
#   docker buildx
#
# Usage:
#   export AWS_ACCOUNT_ID=123456789012
#   export AWS_REGION=us-east-1
#   export ECS_CLUSTER=whatsagent-prod
#   ./infra/scripts/deploy.sh

set -euo pipefail

: "${AWS_ACCOUNT_ID:?}"
: "${AWS_REGION:?}"
: "${ECS_CLUSTER:=whatsagent-prod}"

ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
ECR_REPOSITORY="whatsagent-api"
IMAGE_TAG=$(git rev-parse --short HEAD)
IMAGE_URI="${ECR_REGISTRY}/${ECR_REPOSITORY}:${IMAGE_TAG}"

echo "==> Logging in to ECR..."
aws ecr get-login-password --region "${AWS_REGION}" \
  | docker login --username AWS --password-stdin "${ECR_REGISTRY}"

echo "==> Creating ECR repository (idempotent)..."
aws ecr create-repository \
  --repository-name "${ECR_REPOSITORY}" \
  --region "${AWS_REGION}" \
  --image-scanning-configuration scanOnPush=true \
  --encryption-configuration encryptionType=AES256 2>/dev/null || true

echo "==> Building image: ${IMAGE_URI}..."
docker build \
  -t "${IMAGE_URI}" \
  -t "${ECR_REGISTRY}/${ECR_REPOSITORY}:latest" \
  apps/api

echo "==> Pushing image..."
docker push "${IMAGE_URI}"
docker push "${ECR_REGISTRY}/${ECR_REPOSITORY}:latest"

echo "==> Creating CloudWatch log groups (idempotent)..."
for svc in api worker beat; do
  aws logs create-log-group \
    --log-group-name "/ecs/whatsagent-${svc}" \
    --region "${AWS_REGION}" 2>/dev/null || true
  aws logs put-retention-policy \
    --log-group-name "/ecs/whatsagent-${svc}" \
    --retention-in-days 30 \
    --region "${AWS_REGION}" 2>/dev/null || true
done

echo "==> Registering task definitions..."
for svc in api worker beat; do
  TASK_DEF=$(cat "infra/ecs/task-definition-${svc}.json" \
    | sed "s/ACCOUNT_ID/${AWS_ACCOUNT_ID}/g" \
    | sed "s/REGION/${AWS_REGION}/g")

  TASK_DEF=$(echo "${TASK_DEF}" \
    | python3 -c "
import json, sys
td = json.load(sys.stdin)
for c in td['containerDefinitions']:
    if c['name'] == 'whatsagent-${svc}':
        c['image'] = '${IMAGE_URI}'
print(json.dumps(td))")

  aws ecs register-task-definition \
    --cli-input-json "${TASK_DEF}" \
    --region "${AWS_REGION}" \
    --query 'taskDefinition.taskDefinitionArn' \
    --output text
done

echo "==> Updating ECS services..."
for svc in api worker beat; do
  FAMILY="whatsagent-${svc}"
  LATEST_REVISION=$(aws ecs describe-task-definition \
    --task-definition "${FAMILY}" \
    --region "${AWS_REGION}" \
    --query 'taskDefinition.taskDefinitionArn' \
    --output text)

  aws ecs update-service \
    --cluster "${ECS_CLUSTER}" \
    --service "${FAMILY}" \
    --task-definition "${LATEST_REVISION}" \
    --force-new-deployment \
    --region "${AWS_REGION}" \
    --output text \
    --query 'service.serviceName' \
    && echo "  Updated: ${FAMILY}"
done

echo "==> Deploy initiated. Monitor at:"
echo "    https://${AWS_REGION}.console.aws.amazon.com/ecs/v2/clusters/${ECS_CLUSTER}/services"
