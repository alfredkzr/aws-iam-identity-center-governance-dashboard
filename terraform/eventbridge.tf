# -----------------------------------------------------------------------------
# EventBridge Scheduler — Trigger Step Functions crawler on a schedule
# -----------------------------------------------------------------------------

resource "aws_scheduler_schedule" "crawler" {
  name       = "${var.resource_prefix}-crawler-schedule"
  group_name = "default"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression          = "rate(${var.crawler_schedule_interval})"
  schedule_expression_timezone = "UTC"

  target {
    arn      = aws_sfn_state_machine.crawler.arn
    role_arn = aws_iam_role.scheduler.arn
    input    = "{}"
  }
}

# -----------------------------------------------------------------------------
# EventBridge Scheduler IAM Role
# -----------------------------------------------------------------------------

resource "aws_iam_role" "scheduler" {
  name = "${var.resource_prefix}-scheduler-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "scheduler.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "scheduler_policy" {
  name = "${var.resource_prefix}-scheduler-policy"
  role = aws_iam_role.scheduler.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "StartStepFunction"
        Effect = "Allow"
        Action = [
          "states:StartExecution"
        ]
        Resource = aws_sfn_state_machine.crawler.arn
      }
    ]
  })
}
