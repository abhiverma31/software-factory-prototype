resource "aws_ecr_repository" "django" {
  name         = local.django_ecr_repo_name
  force_delete = true

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "django" {
  repository = aws_ecr_repository.django.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep the last three prototype images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 3
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

resource "aws_ecr_repository" "worker" {
  name         = local.worker_ecr_repo_name
  force_delete = true

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "worker" {
  repository = aws_ecr_repository.worker.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep the last three prototype worker images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 3
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

resource "aws_s3_bucket" "status" {
  bucket        = local.status_bucket_name
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "status" {
  bucket = aws_s3_bucket.status.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "status" {
  bucket = aws_s3_bucket.status.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "status" {
  bucket = aws_s3_bucket.status.id

  versioning_configuration {
    status = "Disabled"
  }
}

resource "aws_cloudwatch_log_group" "django" {
  name              = "/aws/lambda/${local.django_function_name}"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "factory" {
  name              = "/${var.project_name}/${var.environment}/factory"
  retention_in_days = var.log_retention_days
}

resource "aws_ecs_cluster" "factory" {
  name = "${local.name_prefix}-cluster"
}

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

data "aws_iam_policy_document" "ecs_tasks_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "worker_execution" {
  name               = "${local.name_prefix}-worker-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume_role.json
}

resource "aws_iam_role_policy_attachment" "worker_execution" {
  role       = aws_iam_role.worker_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "worker_task" {
  name               = "${local.name_prefix}-worker-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume_role.json
}

data "aws_iam_policy_document" "worker_status_s3" {
  statement {
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
    ]

    resources = [
      "${aws_s3_bucket.status.arn}/factory/status.json",
    ]
  }
}

resource "aws_iam_role_policy" "worker_status_s3" {
  name   = "${local.name_prefix}-worker-status-s3"
  role   = aws_iam_role.worker_task.id
  policy = data.aws_iam_policy_document.worker_status_s3.json
}

resource "aws_ecs_task_definition" "worker" {
  family                   = "${local.name_prefix}-worker"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.worker_execution.arn
  task_role_arn            = aws_iam_role.worker_task.arn

  container_definitions = jsonencode([
    {
      name      = "worker"
      image     = "${aws_ecr_repository.worker.repository_url}:latest"
      essential = true

      environment = [
        {
          name  = "FACTORY_STATUS_BACKEND"
          value = "s3"
        },
        {
          name  = "FACTORY_STATUS_BUCKET"
          value = aws_s3_bucket.status.bucket
        },
        {
          name  = "FACTORY_STATUS_KEY"
          value = "factory/status.json"
        },
        {
          name  = "FACTORY_REPO_URL"
          value = "https://github.com/${var.github_repository}.git"
        },
        {
          name  = "FACTORY_WORKSPACE_DIR"
          value = "/tmp/software-factory-workspace"
        },
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.factory.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "worker"
        }
      }
    }
  ])
}

data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "django_lambda" {
  name               = "${local.name_prefix}-django-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

resource "aws_iam_role_policy_attachment" "django_basic_execution" {
  role       = aws_iam_role.django_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

data "aws_iam_policy_document" "django_status_s3" {
  statement {
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
    ]

    resources = [
      "${aws_s3_bucket.status.arn}/factory/status.json",
    ]
  }
}

resource "aws_iam_role_policy" "django_status_s3" {
  name   = "${local.name_prefix}-django-status-s3"
  role   = aws_iam_role.django_lambda.id
  policy = data.aws_iam_policy_document.django_status_s3.json
}

data "aws_iam_policy_document" "django_run_worker" {
  statement {
    actions = [
      "ecs:RunTask",
    ]

    resources = [
      aws_ecs_task_definition.worker.arn,
    ]
  }

  statement {
    actions = [
      "iam:PassRole",
    ]

    resources = [
      aws_iam_role.worker_execution.arn,
      aws_iam_role.worker_task.arn,
    ]
  }
}

resource "aws_iam_role_policy" "django_run_worker" {
  name   = "${local.name_prefix}-django-run-worker"
  role   = aws_iam_role.django_lambda.id
  policy = data.aws_iam_policy_document.django_run_worker.json
}

resource "aws_lambda_function" "django" {
  count = var.django_image_uri != "" ? 1 : 0

  function_name = local.django_function_name
  role          = aws_iam_role.django_lambda.arn
  package_type  = "Image"
  image_uri     = var.django_image_uri
  architectures = ["x86_64"]
  memory_size   = var.django_memory_mb
  timeout       = var.django_timeout_seconds

  environment {
    variables = {
      DJANGO_ALLOWED_HOSTS          = "*"
      DJANGO_DEBUG                  = "false"
      DJANGO_SECRET_KEY             = "prototype-lambda-secret"
      DEMO_EPOCH_FILE               = "/tmp/demo_epoch.txt"
      FACTORY_RUNS_DIR              = "/tmp/factory_runs"
      FACTORY_STATUS_FILE           = "/tmp/factory_status.json"
      FACTORY_STATUS_BACKEND        = "s3"
      FACTORY_STATUS_BUCKET         = aws_s3_bucket.status.bucket
      FACTORY_STATUS_KEY            = "factory/status.json"
      FACTORY_RUNNER_BACKEND        = "ecs"
      FACTORY_ECS_CLUSTER           = aws_ecs_cluster.factory.name
      FACTORY_ECS_TASK_DEFINITION   = aws_ecs_task_definition.worker.arn
      FACTORY_ECS_SUBNETS           = join(",", data.aws_subnets.default.ids)
      FACTORY_ECS_ASSIGN_PUBLIC_IP  = "ENABLED"
      FACTORY_WORKER_CONTAINER_NAME = "worker"
      SOFTWARE_FACTORY_SKIP_RESET   = "1"
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.django,
    aws_iam_role_policy_attachment.django_basic_execution,
    aws_iam_role_policy.django_status_s3,
    aws_iam_role_policy.django_run_worker,
  ]

  lifecycle {
    ignore_changes = [image_uri]
  }
}

resource "aws_lambda_function_url" "django" {
  count = var.django_image_uri != "" ? 1 : 0

  function_name      = aws_lambda_function.django[0].function_name
  authorization_type = "NONE"
}

resource "aws_lambda_permission" "django_function_url_public" {
  count = var.django_image_uri != "" ? 1 : 0

  statement_id           = "AllowPublicFunctionUrlInvoke"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.django[0].function_name
  principal              = "*"
  function_url_auth_type = "NONE"
}
