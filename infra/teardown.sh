#!/usr/bin/env bash
# Removes everything infra/deploy.sh created, including the ECR images and the
# secret (no recovery window). Usage: infra/teardown.sh   (Terraform asks to confirm)
set -euo pipefail
cd "$(dirname "$0")/.."
export AWS_REGION="${AWS_REGION:-us-east-1}" AWS_DEFAULT_REGION="${AWS_REGION:-us-east-1}"
terraform -chdir=infra/terraform init -input=false >/dev/null
terraform -chdir=infra/terraform destroy "$@"
echo "Check nothing tagged project=ai-research-assistant is left:"
echo "  aws resourcegroupstaggingapi get-resources --tag-filters Key=project,Values=ai-research-assistant"
