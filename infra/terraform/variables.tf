variable "app_name" {
  description = "Name used for the cluster, service, task family, roles and tags."
  type        = string
  default     = "ai-research-assistant"
}

variable "region" {
  description = "AWS region for everything, including the Bedrock inference profile."
  type        = string
  default     = "us-east-1"
}

variable "image_tag" {
  description = "Tag of the image in ECR to run. infra/deploy.sh passes the git commit."
  type        = string
  default     = "latest"
}

variable "desired_count" {
  description = "Number of tasks. Raise it to scale out, with no code change (R1.5)."
  type        = number
  default     = 1
}

variable "task_cpu" {
  description = "Fargate CPU units (512 = 0.5 vCPU)."
  type        = number
  default     = 512
}

variable "task_memory" {
  description = "Fargate memory in MiB; must pair validly with task_cpu."
  type        = number
  default     = 1024
}

variable "llm_providers" {
  description = "Providers in the model picker; the first is the default."
  type        = string
  default     = "bedrock,groq"
}

variable "bedrock_model_id" {
  description = "Inference profile id the app calls."
  type        = string
  default     = "us.anthropic.claude-opus-4-6-v1"
}

variable "bedrock_foundation_model_id" {
  description = "Foundation model behind the inference profile, for the IAM policy."
  type        = string
  default     = "anthropic.claude-opus-4-6-v1"
}

variable "groq_model" {
  type    = string
  default = "openai/gpt-oss-120b"
}

variable "certificate_arn" {
  description = "Optional ACM certificate for a domain you own. When set, the ALB serves HTTPS and redirects HTTP."
  type        = string
  default     = ""
}

variable "github_repo" {
  description = "owner/name of the repository allowed to deploy through OIDC (R1.4)."
  type        = string
  default     = "shkroyas/ai-research-assistant"
}

variable "create_github_oidc_provider" {
  description = "Set to false if the account already has the token.actions.githubusercontent.com provider."
  type        = bool
  default     = true
}

variable "budget_email" {
  description = "Optional email for AWS Budget alerts. Empty skips the budget."
  type        = string
  default     = ""
}

variable "budget_limit_usd" {
  type    = number
  default = 30
}
