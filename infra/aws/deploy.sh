#!/usr/bin/env bash
set -euo pipefail

#
# deploy.sh — Build, push, and deploy SFA to AWS ECS Fargate
#
# Usage:
#   ./deploy.sh                    # Deploy with defaults
#   ./deploy.sh --stack-name my-sfa --region us-west-2
#
# Prerequisites:
#   - AWS CLI configured with appropriate credentials
#   - Docker installed and running
#   - Groq API key stored in Secrets Manager (or will be created by CloudFormation)
#

STACK_NAME="${STACK_NAME:-sfa-prod}"
AWS_REGION="${AWS_REGION:-us-east-1}"
API_IMAGE_TAG="${API_IMAGE_TAG:-latest}"
UI_IMAGE_TAG="${UI_IMAGE_TAG:-latest}"

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --stack-name) STACK_NAME="$2"; shift 2 ;;
    --region) AWS_REGION="$2"; shift 2 ;;
    --api-tag) API_IMAGE_TAG="$2"; shift 2 ;;
    --ui-tag) UI_IMAGE_TAG="$2"; shift 2 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
CFN_TEMPLATE="${SCRIPT_DIR}/cloudformation.yml"

echo "================================================"
echo "  System Failures AI Agent — AWS Deployment"
echo "================================================"
echo "Stack:    ${STACK_NAME}"
echo "Region:   ${AWS_REGION}"
echo "API Tag:  ${API_IMAGE_TAG}"
echo "UI Tag:   ${UI_IMAGE_TAG}"
echo ""

# ── Step 1: Get AWS Account ID ──────────────────────────────────

AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --region "${AWS_REGION}")
echo "[1/6] AWS Account: ${AWS_ACCOUNT_ID}"

ECR_API_REPO="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${STACK_NAME}-api"
ECR_UI_REPO="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${STACK_NAME}-ui"

# ── Step 2: Deploy/update CloudFormation stack ──────────────────

echo "[2/6] Deploying CloudFormation stack..."
aws cloudformation deploy \
  --template-file "${CFN_TEMPLATE}" \
  --stack-name "${STACK_NAME}" \
  --region "${AWS_REGION}" \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    EnvironmentName="${STACK_NAME}" \
    ApiImageTag="${API_IMAGE_TAG}" \
    UiImageTag="${UI_IMAGE_TAG}" \
  --no-fail-on-empty-changeset

echo "    CloudFormation stack deployed."

# ── Step 3: Login to ECR ────────────────────────────────────────

echo "[3/6] Logging into ECR..."
aws ecr get-login-password --region "${AWS_REGION}" | \
  docker login --username AWS --password-stdin \
  "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

# ── Step 4: Build and push Docker images ────────────────────────

echo "[4/6] Building and pushing API image..."
docker build \
  -f "${PROJECT_ROOT}/docker/api.Dockerfile" \
  -t "${ECR_API_REPO}:${API_IMAGE_TAG}" \
  "${PROJECT_ROOT}"
docker push "${ECR_API_REPO}:${API_IMAGE_TAG}"

echo "[5/6] Building and pushing UI image..."
docker build \
  -f "${PROJECT_ROOT}/docker/ui.Dockerfile" \
  -t "${ECR_UI_REPO}:${UI_IMAGE_TAG}" \
  "${PROJECT_ROOT}"
docker push "${ECR_UI_REPO}:${UI_IMAGE_TAG}"

# ── Step 6: Force new deployment ────────────────────────────────

echo "[6/6] Forcing new ECS deployment..."
aws ecs update-service \
  --cluster "${STACK_NAME}-cluster" \
  --service "${STACK_NAME}-api" \
  --force-new-deployment \
  --region "${AWS_REGION}" \
  --no-cli-pager

aws ecs update-service \
  --cluster "${STACK_NAME}-cluster" \
  --service "${STACK_NAME}-ui" \
  --force-new-deployment \
  --region "${AWS_REGION}" \
  --no-cli-pager

# ── Done ────────────────────────────────────────────────────────

ALB_URL=$(aws cloudformation describe-stacks \
  --stack-name "${STACK_NAME}" \
  --region "${AWS_REGION}" \
  --query "Stacks[0].Outputs[?OutputKey=='ALBURL'].OutputValue" \
  --output text)

echo ""
echo "================================================"
echo "  Deployment Complete!"
echo "================================================"
echo "Application URL: ${ALB_URL}"
echo "API endpoint:    ${ALB_URL}/api/v1"
echo "Health check:    ${ALB_URL}/health"
echo ""
echo "To update the Groq API key:"
echo "  aws secretsmanager put-secret-value \\"
echo "    --secret-id ${STACK_NAME}/groq-api-key \\"
echo "    --secret-string 'YOUR_GROQ_API_KEY' \\"
echo "    --region ${AWS_REGION}"
echo ""
echo "To view logs:"
echo "  aws logs tail /ecs/${STACK_NAME}/api --follow --region ${AWS_REGION}"
echo "  aws logs tail /ecs/${STACK_NAME}/ui --follow --region ${AWS_REGION}"