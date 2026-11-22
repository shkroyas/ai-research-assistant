# 003 AWS deployment: requirements

**Status:** Done, live in us-east-1. Design in [design.md](design.md), cost in [cost.md](cost.md), tasks in [tasks.md](tasks.md).

## Goal

Run the app on AWS behind a public HTTPS-capable address, with no keys stored in the image or the repository, and deploy new versions from GitHub.

## Acceptance criteria (draft)

- **R1.1** The container image from spec 002 is stored in Amazon ECR in `us-east-1`.
- **R1.2** The app runs on ECS Fargate behind an Application Load Balancer. Streamlit needs WebSockets and sticky sessions, which the load balancer supports.
- **R1.3** Groq and Tavily keys come from AWS Secrets Manager. Bedrock access comes from the task's IAM role, limited to `bedrock:InvokeModel` on the chosen model, so no AWS keys are stored at all.
- **R1.4** GitHub Actions deploys a new image on a push to `main` through OIDC, with no long-lived AWS keys in GitHub.
- **R1.5** One task by default. Scaling out means raising the task count, with no code change.
- **R1.6** Monthly cost is estimated before anything is created.

## Alternative

A single EC2 instance running `docker compose`. It is cheaper and simpler, but has no rolling deploys and no automatic recovery. This is the fallback if the Fargate cost estimate is too high for a demo.

## Open questions

- Budget limit for the demo period. See [cost.md](cost.md) for the estimate.
- Whether the deployment should stay up after the assignment is reviewed.
