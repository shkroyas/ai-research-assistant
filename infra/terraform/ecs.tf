resource "aws_ecs_cluster" "main" {
  name = var.app_name
}

resource "aws_ecs_task_definition" "app" {
  family                   = var.app_name
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  runtime_platform {
    cpu_architecture        = "X86_64"
    operating_system_family = "LINUX"
  }

  container_definitions = jsonencode([{
    name         = "app"
    image        = "${aws_ecr_repository.app.repository_url}:${var.image_tag}"
    essential    = true
    portMappings = [{ containerPort = 8501, protocol = "tcp" }]
    environment = [
      { name = "LLM_PROVIDERS", value = var.llm_providers },
      { name = "AWS_REGION", value = var.region },
      { name = "BEDROCK_MODEL_ID", value = var.bedrock_model_id },
      { name = "BEDROCK_API", value = "invoke" },
      { name = "GROQ_MODEL", value = var.groq_model },
      { name = "SCRAPE_PAGES", value = "true" },
      { name = "READ_PDFS", value = "false" },
      { name = "LOG_LEVEL", value = "INFO" },
    ]
    secrets = [
      { name = "GROQ_API_KEYS", valueFrom = "${aws_secretsmanager_secret.api_keys.arn}:GROQ_API_KEYS::" },
      { name = "TAVILY_API_KEY", valueFrom = "${aws_secretsmanager_secret.api_keys.arn}:TAVILY_API_KEY::" },
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.app.name
        awslogs-region        = var.region
        awslogs-stream-prefix = "app"
      }
    }
  }])
}

resource "aws_ecs_service" "app" {
  name                              = var.app_name
  cluster                           = aws_ecs_cluster.main.id
  task_definition                   = aws_ecs_task_definition.app.arn
  desired_count                     = var.desired_count
  launch_type                       = "FARGATE"
  health_check_grace_period_seconds = 60
  propagate_tags                    = "SERVICE"

  # Rolling deploys: the new task must be healthy before the old one stops,
  # and a failing image rolls back by itself.
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  network_configuration {
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.task.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.app.arn
    container_name   = "app"
    container_port   = 8501
  }

  # deploy.yml rolls out new task definitions from main; a later terraform apply
  # (for example to change desired_count) must not roll the image back.
  lifecycle {
    ignore_changes = [task_definition]
  }

  depends_on = [aws_lb_listener.http]
}
