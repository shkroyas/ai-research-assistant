resource "aws_lb" "main" {
  name               = var.app_name
  load_balancer_type = "application"
  internal           = false
  subnets            = aws_subnet.public[*].id
  security_groups    = [aws_security_group.alb.id]
  # Streamlit keeps a WebSocket open for the whole session.
  idle_timeout = 300
}

resource "aws_lb_target_group" "app" {
  name                 = var.app_name
  vpc_id               = aws_vpc.main.id
  port                 = 8501
  protocol             = "HTTP"
  target_type          = "ip"
  deregistration_delay = 30

  health_check {
    path                = "/_stcore/health"
    interval            = 15
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  # Sticky sessions keep a browser on the task that holds its Streamlit session.
  stickiness {
    enabled         = true
    type            = "lb_cookie"
    cookie_duration = 86400
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = local.use_https ? "redirect" : "forward"
    target_group_arn = local.use_https ? null : aws_lb_target_group.app.arn

    dynamic "redirect" {
      for_each = local.use_https ? [1] : []
      content {
        protocol    = "HTTPS"
        port        = "443"
        status_code = "HTTP_301"
      }
    }
  }
}

resource "aws_lb_listener" "https" {
  count             = local.use_https ? 1 : 0
  load_balancer_arn = aws_lb.main.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
}

locals {
  use_https = var.certificate_arn != ""
}
