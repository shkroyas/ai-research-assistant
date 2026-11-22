# 003 AWS deployment: cost estimate (R1.6)

**Status:** Estimate, made before anything is created on AWS.

On-demand list prices in `us-east-1`, November 2026. They leave out any free tier or account credits, so a newer account may pay less. Bedrock tokens are left out because they cost the same on either option (see the end of this page).

## Option A: ECS Fargate behind an Application Load Balancer (the main plan)

| Item | Sizing | Per day | Per month |
| --- | --- | --- | --- |
| Fargate task | 0.5 vCPU, 1 GB, Linux/x86, 1 task | $0.59 | $18.0 |
| Application Load Balancer | hourly charge plus about 1 LCU | $0.73 | $22.3 |
| Public IPv4 addresses | 2 for the load balancer, 1 for the task | $0.36 | $11.0 |
| Secrets Manager | 1 secret holding the Groq and Tavily keys as JSON | $0.01 | $0.4 |
| ECR | one image of about 0.5 GB, older images expire | under $0.01 | $0.1 |
| CloudWatch Logs | 7 day retention, low volume | $0.02 | $0.5 |
| **Total** | | **about $1.70** | **about $52** |

The task runs in public subnets with a public IP so it can pull the image and reach Groq and Tavily without a NAT gateway, which would add about $33 a month. Its security group only accepts traffic from the load balancer.

## Option B: one EC2 instance running `docker compose` (the fallback)

| Item | Sizing | Per day | Per month |
| --- | --- | --- | --- |
| EC2 instance | t3.small, 2 vCPU, 2 GB | $0.50 | $15.2 |
| EBS volume | 20 GB gp3 | $0.05 | $1.6 |
| Public IPv4 address | 1 Elastic IP | $0.12 | $3.7 |
| **Total** | | **about $0.67** | **about $20** |

It has no load balancer, so there are no rolling deploys, no automatic recovery if the instance fails, and HTTPS needs a reverse proxy such as Caddy on the instance.

## The demo window

The app must stay up until at least one week after the deadline of Monday 23 November 2026, so from 22 November to about 1 December.

| Option | 10 days | 14 days |
| --- | --- | --- |
| A, Fargate and ALB | about $17 | about $24 |
| B, single EC2 | about $7 | about $10 |

## Bedrock usage

Bedrock bills per token, whichever option runs the app. Claude Opus 4.6 costs $5 per million input tokens and $25 per million output tokens. One brief with a revision round is roughly 40,000 input and 8,000 output tokens, so about $0.40. That is an estimate, not a measurement. Groq runs on free keys and costs nothing.

## Guard rails

- An AWS Budget of $30 a month with email alerts at 50%, 80% and 100%.
- Every resource is tagged `project=ai-research-assistant`, so the bill can be filtered and the teardown can find everything.
- `infra/teardown.sh` runs `terraform destroy`, which removes everything in one step after the demo window.
