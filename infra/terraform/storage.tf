# The image repository and the secret. infra/deploy.sh creates these first, then
# writes the key values with the AWS CLI so they never enter the Terraform state.

resource "aws_ecr_repository" "app" {
  name                 = var.app_name
  image_tag_mutability = "MUTABLE"
  force_delete         = true # teardown removes the images too

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "app" {
  repository = aws_ecr_repository.app.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep the last 5 images"
      selection    = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 5 }
      action       = { type = "expire" }
    }]
  })
}

# Holds GROQ_API_KEYS and TAVILY_API_KEY as JSON (R1.3).
resource "aws_secretsmanager_secret" "api_keys" {
  name                    = "${var.app_name}/api-keys"
  description             = "Groq and Tavily API keys for the app"
  recovery_window_in_days = 0 # teardown deletes it at once
}

resource "aws_cloudwatch_log_group" "app" {
  name              = "/ecs/${var.app_name}"
  retention_in_days = 7
}
