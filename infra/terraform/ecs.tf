# ECS skeleton — cluster + per-service task definitions wired to the log
# groups defined in main.tf. Networking (VPC, subnets, SG, ALB) is intentionally
# *not* in this file yet: the pilot stack reuses a hand-built VPC and ALB, and
# we'll add them in a separate `network.tf` after `terraform import`.
#
# This file is enough to:
#   - own the cluster (so future services land in it via Terraform)
#   - own the task definitions for api/worker/beat (so image rollouts go
#     through `terraform apply -var api_image=...:newtag`)

resource "aws_ecs_cluster" "main" {
  name = "${local.name_prefix}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

# --- IAM ----------------------------------------------------------------------
# Execution role: pulls images + writes logs (assumed by the ECS agent).
# Task role: what the *container* assumes — keep distinct so we can grant
# per-service permissions (e.g. only the worker can read the WhatsApp token
# secret) without inflating the execution role.

data "aws_iam_policy_document" "ecs_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "task_execution" {
  name               = "${local.name_prefix}-task-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
}

resource "aws_iam_role_policy_attachment" "task_execution_managed" {
  role       = aws_iam_role.task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "task" {
  name               = "${local.name_prefix}-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
}

# --- Task definitions ---------------------------------------------------------
# Containers are minimal — env wiring goes through the existing JSON task-defs
# in infra/ecs/ until we finish importing those. The point right now is just
# that Terraform owns the *revision* on each apply.

locals {
  common_logs = {
    logDriver = "awslogs"
    options = {
      "awslogs-region"        = var.aws_region
      "awslogs-stream-prefix" = "ecs"
    }
  }
}

resource "aws_ecs_task_definition" "api" {
  family                   = "${local.name_prefix}-api"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.task_execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([
    {
      name      = "api"
      image     = var.api_image
      essential = true
      portMappings = [{ containerPort = 8000, hostPort = 8000 }]
      logConfiguration = merge(local.common_logs, {
        options = merge(local.common_logs.options, {
          "awslogs-group" = aws_cloudwatch_log_group.api.name
        })
      })
    }
  ])
}

resource "aws_ecs_task_definition" "worker" {
  family                   = "${local.name_prefix}-worker"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.task_execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([
    {
      name      = "worker"
      image     = var.worker_image
      essential = true
      logConfiguration = merge(local.common_logs, {
        options = merge(local.common_logs.options, {
          "awslogs-group" = aws_cloudwatch_log_group.worker.name
        })
      })
    }
  ])
}

resource "aws_ecs_task_definition" "beat" {
  family                   = "${local.name_prefix}-beat"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.task_execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([
    {
      name      = "beat"
      image     = var.beat_image
      essential = true
      logConfiguration = merge(local.common_logs, {
        options = merge(local.common_logs.options, {
          "awslogs-group" = aws_cloudwatch_log_group.beat.name
        })
      })
    }
  ])
}

output "cluster_name" {
  value = aws_ecs_cluster.main.name
}
