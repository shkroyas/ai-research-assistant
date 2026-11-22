#!/usr/bin/env bash
# Builds the image, stores the API keys in Secrets Manager and applies the
# Terraform in infra/terraform (spec 003). Safe to run again.
#
# Usage:  infra/deploy.sh                                  (reads keys from ./.env)
#         BUDGET_EMAIL=you@example.com infra/deploy.sh      (adds the $30 budget alert)
#         CERTIFICATE_ARN=arn:aws:acm:... infra/deploy.sh   (HTTPS on your own domain)
set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
ENV_FILE="${ENV_FILE:-.env}"
export AWS_REGION="$REGION" AWS_DEFAULT_REGION="$REGION" TF_VAR_region="$REGION"

cd "$(dirname "$0")/.."
ROOT="$PWD"
TF="terraform -chdir=infra/terraform"
for tool in aws docker terraform python3; do
  command -v "$tool" >/dev/null || { echo "$tool not found" >&2; exit 1; }
done
[ -f "$ENV_FILE" ] || { echo "$ENV_FILE not found; copy .env.example and add your keys" >&2; exit 1; }

ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
TAG="$(git rev-parse --short=12 HEAD 2>/dev/null || date +%Y%m%d%H%M%S)"
export TF_VAR_image_tag="$TAG"
echo "Account $ACCOUNT, region $REGION, image tag $TAG"

# Remember optional settings, so a later run without them does not remove them.
[ -n "${BUDGET_EMAIL:-}" ] && printf 'budget_email = "%s"\n' "$BUDGET_EMAIL" > infra/terraform/budget.auto.tfvars
[ -n "${CERTIFICATE_ARN:-}" ] && printf 'certificate_arn = "%s"\n' "$CERTIFICATE_ARN" > infra/terraform/https.auto.tfvars

$TF init -input=false >/dev/null

# Reuse the account's GitHub OIDC provider if one already exists outside this state.
OIDC_ARN="arn:aws:iam::$ACCOUNT:oidc-provider/token.actions.githubusercontent.com"
if aws iam get-open-id-connect-provider --open-id-connect-provider-arn "$OIDC_ARN" >/dev/null 2>&1 &&
   ! $TF state list 2>/dev/null | grep -q '^aws_iam_openid_connect_provider.github'; then
  export TF_VAR_create_github_oidc_provider=false
fi

# 1. The image repository and the empty secret come first (R1.1).
$TF apply -input=false -auto-approve \
  -target=aws_ecr_repository.app -target=aws_ecr_lifecycle_policy.app \
  -target=aws_secretsmanager_secret.api_keys
REPO_URL="$($TF output -raw ecr_repository_url)"
SECRET_ARN="$($TF output -raw secret_arn)"

# 2. Key values go straight from .env to Secrets Manager through a private temp file,
#    so they are never printed, passed as arguments or stored in Terraform state (R1.3).
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
aws secretsmanager put-secret-value --secret-id "$SECRET_ARN" --secret-string "file://$SECRET_FILE" >/dev/null
echo "Secret stored"

# 3. Build and push the image from spec 002.
aws ecr get-login-password | docker login --username AWS --password-stdin "${REPO_URL%%/*}" >/dev/null
docker build --platform linux/amd64 -t "$REPO_URL:$TAG" "$ROOT"
docker push "$REPO_URL:$TAG"

# 4. Everything else: network, load balancer, ECS, IAM, logs and the budget.
$TF plan -input=false -out=deploy.tfplan
$TF apply -input=false deploy.tfplan
rm -f infra/terraform/deploy.tfplan

$TF output
