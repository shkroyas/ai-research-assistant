#!/usr/bin/env bash
# Builds the image, stores the API keys in Secrets Manager and deploys the
# CloudFormation stack (spec 003). Safe to run again: every step is idempotent.
#
# Usage:  infra/deploy.sh                 (reads keys from ./.env)
#         BUDGET_EMAIL=you@example.com infra/deploy.sh
#         CERTIFICATE_ARN=arn:aws:acm:... infra/deploy.sh   (HTTPS on your own domain)
set -euo pipefail

APP="${APP:-ai-research-assistant}"
REGION="${AWS_REGION:-us-east-1}"
ENV_FILE="${ENV_FILE:-.env}"
STACK="$APP"
export AWS_REGION="$REGION" AWS_DEFAULT_REGION="$REGION"

cd "$(dirname "$0")/.."
command -v aws >/dev/null || { echo "aws CLI not found" >&2; exit 1; }
command -v docker >/dev/null || { echo "docker not found" >&2; exit 1; }
[ -f "$ENV_FILE" ] || { echo "$ENV_FILE not found; copy .env.example and add your keys" >&2; exit 1; }

ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
REGISTRY="$ACCOUNT.dkr.ecr.$REGION.amazonaws.com"
TAG="$(git rev-parse --short=12 HEAD 2>/dev/null || date +%Y%m%d%H%M%S)"
IMAGE="$REGISTRY/$APP:$TAG"
echo "Account $ACCOUNT, region $REGION, image tag $TAG"

# 1. ECR repository (R1.1), keeping the last 5 images.
if ! aws ecr describe-repositories --repository-names "$APP" >/dev/null 2>&1; then
  echo "Creating ECR repository $APP"
  aws ecr create-repository --repository-name "$APP" \
    --image-scanning-configuration scanOnPush=true \
    --tags Key=project,Value="$APP" >/dev/null
fi
aws ecr put-lifecycle-policy --repository-name "$APP" --lifecycle-policy-text \
  '{"rules":[{"rulePriority":1,"description":"Keep the last 5 images","selection":{"tagStatus":"any","countType":"imageCountMoreThan","countNumber":5},"action":{"type":"expire"}}]}' >/dev/null

# 2. One secret with the Groq and Tavily keys (R1.3). Values are read from .env and
#    written through a private temp file; they are never printed or passed as arguments.
SECRET_FILE="$(mktemp)"; chmod 600 "$SECRET_FILE"; trap 'rm -f "$SECRET_FILE"' EXIT
python3 - "$ENV_FILE" "$SECRET_FILE" <<'PY'
import json, sys
values = {}
for line in open(sys.argv[1], encoding="utf-8"):
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, _, value = line.partition("=")
    values[key.strip()] = value.strip().strip('"').strip("'")
secret = {k: values.get(k, "") for k in ("GROQ_API_KEYS", "TAVILY_API_KEY")}
for k, v in secret.items():
    print(f"  {k}: {'set' if v else 'empty'}")
json.dump(secret, open(sys.argv[2], "w"))
PY
SECRET_NAME="$APP/api-keys"
if aws secretsmanager describe-secret --secret-id "$SECRET_NAME" >/dev/null 2>&1; then
  aws secretsmanager put-secret-value --secret-id "$SECRET_NAME" --secret-string "file://$SECRET_FILE" >/dev/null
else
  aws secretsmanager create-secret --name "$SECRET_NAME" --secret-string "file://$SECRET_FILE" \
    --tags Key=project,Value="$APP" >/dev/null
fi
SECRET_ARN="$(aws secretsmanager describe-secret --secret-id "$SECRET_NAME" --query ARN --output text)"
echo "Secret $SECRET_NAME stored"

# 3. Build and push the image from spec 002.
aws ecr get-login-password | docker login --username AWS --password-stdin "$REGISTRY" >/dev/null
docker build --platform linux/amd64 -t "$IMAGE" .
docker push "$IMAGE"

# 4. Reuse the account's GitHub OIDC provider if one exists outside this stack.
CREATE_OIDC=true
OIDC_ARN="arn:aws:iam::$ACCOUNT:oidc-provider/token.actions.githubusercontent.com"
if aws iam get-open-id-connect-provider --open-id-connect-provider-arn "$OIDC_ARN" >/dev/null 2>&1 &&
   ! aws cloudformation describe-stack-resource --stack-name "$STACK" \
       --logical-resource-id GitHubOidcProvider >/dev/null 2>&1; then
  CREATE_OIDC=false
fi

# 5. The stack itself.
aws cloudformation deploy \
  --stack-name "$STACK" \
  --template-file infra/cloudformation.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --no-fail-on-empty-changeset \
  --tags project="$APP" \
  --parameter-overrides \
    AppName="$APP" \
    ImageUri="$IMAGE" \
    SecretArn="$SECRET_ARN" \
    CreateGitHubOidcProvider="$CREATE_OIDC" \
    BudgetEmail="${BUDGET_EMAIL:-}" \
    CertificateArn="${CERTIFICATE_ARN:-}"

aws cloudformation describe-stacks --stack-name "$STACK" \
  --query 'Stacks[0].Outputs[].[OutputKey,OutputValue]' --output table
