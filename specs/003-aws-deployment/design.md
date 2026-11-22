# 003 AWS deployment: design

## Shape

```
Browser ──HTTP(S)──► Application Load Balancer (2 public subnets, sticky cookie, 300 s idle timeout)
                          │  port 8501, only from the ALB security group
                          ▼
                   ECS Fargate service, 1 task (0.5 vCPU, 1 GB)
                          │  task role: bedrock:InvokeModel on one model
                          ├──► Amazon Bedrock (Claude Opus 4.6 inference profile)
                          └──► Groq, Tavily, web pages (public IP, no NAT gateway)

ECR (image)     Secrets Manager (GROQ_API_KEYS, TAVILY_API_KEY)     CloudWatch Logs (7 days)
GitHub Actions ──OIDC──► deploy role ──► push image, register task definition, update service
```

Everything except the image repository and the secret is one CloudFormation stack, [`infra/cloudformation.yaml`](../../infra/cloudformation.yaml). [`infra/deploy.sh`](../../infra/deploy.sh) creates those two first, so no key value ever appears in the template, its parameters or the stack events.

## Decisions

| Decision | Why | Rejected |
| --- | --- | --- |
| CloudFormation, one stack | Built into AWS, no extra tool to install, and deleting the stack removes everything it made | Terraform (state file to keep), CDK (Node toolchain), console clicks (not repeatable) |
| Public subnets, task with a public IP | Saves the NAT gateway, about $33 a month, which is more than the whole demo | Private subnets with NAT or VPC endpoints |
| One JSON secret | $0.40 a month instead of $0.40 per key; ECS reads single fields with `secret-arn:KEY::` | One secret per key |
| Task role for Bedrock | No AWS keys anywhere; the AnthropicBedrock client picks up the container credentials | Access keys in the secret |
| IAM scoped to the inference profile and its foundation model | The `us.` profile routes to several US regions, so the foundation model ARN uses a region wildcard | `bedrock:*` |
| Sticky `lb_cookie` and 300 s idle timeout | Streamlit keeps session state on one task over a WebSocket | No stickiness (breaks as soon as there are 2 tasks) |
| Rolling deploy, 100% minimum and 200% maximum healthy, circuit breaker | The new task must pass `/_stcore/health` before the old one stops; a bad image rolls back by itself | Stop then start |
| Deploy runs after CI passes on main (`workflow_run`) | A red build never reaches AWS | Deploying on every push |
| OIDC trust limited to `repo:shkroyas/ai-research-assistant:ref:refs/heads/main` | Pull requests and other branches cannot assume the role | Trusting the whole repository |
| HTTPS only when a certificate ARN is given | The ALB's own DNS name cannot have an ACM certificate; with a domain, set `CERTIFICATE_ARN` and HTTP redirects to HTTPS | A self-signed certificate (browser warnings) |
| AWS Budget of $30 inside the stack | Alerts by email and disappears with the teardown | No guard rail on a public URL that spends Bedrock tokens |

## Teardown

`infra/teardown.sh` deletes the stack, then the ECR repository with its images, then the secret without the 7 day recovery window. The planned date is on or after 1 December 2026, a week after the assignment deadline.
