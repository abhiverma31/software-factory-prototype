output "status_bucket_name" {
  description = "Private S3 bucket used for factory status JSON."
  value       = aws_s3_bucket.status.bucket
}

output "aws_region" {
  description = "AWS region used by the stack."
  value       = var.aws_region
}

output "django_ecr_repository_url" {
  description = "ECR repository URL for the Django Lambda container image."
  value       = aws_ecr_repository.django.repository_url
}

output "django_image_uri_latest" {
  description = "Image URI to use for django_image_uri after pushing the latest image."
  value       = "${aws_ecr_repository.django.repository_url}:latest"
}

output "django_function_url" {
  description = "Public Lambda Function URL for the Django UI. Empty until django_image_uri is set."
  value       = try(aws_lambda_function_url.django[0].function_url, "")
}

output "status_object_key" {
  description = "S3 key the app will use for the latest factory status JSON."
  value       = "factory/status.json"
}

output "django_log_group_name" {
  description = "CloudWatch log group for the Django Lambda."
  value       = aws_cloudwatch_log_group.django.name
}

output "factory_log_group_name" {
  description = "CloudWatch log group for the factory worker."
  value       = aws_cloudwatch_log_group.factory.name
}

output "openai_api_key_parameter_name" {
  description = "SSM SecureString parameter name to create outside Terraform for the OpenAI API key."
  value       = local.openai_api_key_parameter_name
}

output "github_token_parameter_name" {
  description = "SSM SecureString parameter name to create outside Terraform for the GitHub token."
  value       = local.github_token_parameter_name
}

output "github_actions_role_arn" {
  description = "IAM role ARN GitHub Actions will assume through OIDC for Django deploys."
  value       = aws_iam_role.github_actions_deploy.arn
}
