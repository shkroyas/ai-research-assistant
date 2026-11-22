output "app_url" {
  description = "Public address of the app."
  value       = "${local.use_https ? "https" : "http"}://${aws_lb.main.dns_name}"
}

output "load_balancer_dns_name" {
  description = "Point a CNAME at this when using your own domain."
  value       = aws_lb.main.dns_name
}

output "deploy_role_arn" {
  description = "Set as the GitHub repository variable AWS_DEPLOY_ROLE_ARN."
  value       = aws_iam_role.deploy.arn
}

output "ecr_repository_url" {
  value = aws_ecr_repository.app.repository_url
}

output "secret_arn" {
  value = aws_secretsmanager_secret.api_keys.arn
}
