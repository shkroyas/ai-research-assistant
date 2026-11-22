#!/usr/bin/env bash
# Removes everything infra/deploy.sh created: the stack (network, load balancer,
# ECS, IAM roles, logs, budget), the ECR repository with its images, and the secret.
# Usage: infra/teardown.sh        (asks first)   infra/teardown.sh -y
set -euo pipefail

APP="${APP:-ai-research-assistant}"
REGION="${AWS_REGION:-us-east-1}"
export AWS_REGION="$REGION" AWS_DEFAULT_REGION="$REGION"

if [ "${1:-}" != "-y" ]; then
  read -r -p "Delete the $APP stack, its ECR images and its secret in $REGION? [y/N] " answer
  [ "$answer" = "y" ] || { echo "Cancelled"; exit 0; }
fi

echo "Deleting stack $APP (takes a few minutes)"
aws cloudformation delete-stack --stack-name "$APP"
aws cloudformation wait stack-delete-complete --stack-name "$APP"

echo "Deleting ECR repository $APP"
aws ecr delete-repository --repository-name "$APP" --force >/dev/null 2>&1 || true

echo "Deleting secret $APP/api-keys"
aws secretsmanager delete-secret --secret-id "$APP/api-keys" \
  --force-delete-without-recovery >/dev/null 2>&1 || true

echo "Done. Check the remaining tagged resources with:"
echo "  aws resourcegroupstaggingapi get-resources --tag-filters Key=project,Values=$APP"
