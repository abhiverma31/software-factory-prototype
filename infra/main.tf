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
      DJANGO_ALLOWED_HOSTS        = "*"
      DJANGO_DEBUG                = "false"
      DJANGO_SECRET_KEY           = "prototype-lambda-secret"
      DEMO_EPOCH_FILE             = "/tmp/demo_epoch.txt"
      FACTORY_RUNS_DIR            = "/tmp/factory_runs"
      FACTORY_STATUS_FILE         = "/tmp/factory_status.json"
      SOFTWARE_FACTORY_SKIP_RESET = "1"
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.django,
    aws_iam_role_policy_attachment.django_basic_execution,
  ]
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
