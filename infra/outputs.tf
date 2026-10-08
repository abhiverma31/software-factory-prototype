output "status_bucket_name" {
  description = "Private S3 bucket used for factory status JSON."
  value       = aws_s3_bucket.status.bucket
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
