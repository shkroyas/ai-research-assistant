# 003 AWS deployment: tasks

1. Estimate the cost before creating anything ([cost.md](cost.md)). R1.6
2. Terraform in `infra/terraform/`: VPC with two public subnets, ALB with sticky sessions, ECR repository, secret, ECS cluster, service and task definition, log group, IAM roles, GitHub OIDC provider and the budget. R1.2, R1.3, R1.5
3. `infra/deploy.sh`: ECR and secret first, key values from `.env`, image build and push, then the full apply. R1.1, R1.3
4. `.github/workflows/deploy.yml`: build, push and roll out after CI passes on main, through OIDC. R1.4
5. First deploy from a machine with AWS credentials; check the health endpoint and run one brief with each provider.
6. Set the repository variable `AWS_DEPLOY_ROLE_ARN` and check that a push to main deploys.
7. On or after 1 December 2026, run `infra/teardown.sh`.
