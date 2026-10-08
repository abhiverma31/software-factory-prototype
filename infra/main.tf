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
  name              = "/${var.project_name}/${var.environment}/django"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "factory" {
  name              = "/${var.project_name}/${var.environment}/factory"
  retention_in_days = var.log_retention_days
}
