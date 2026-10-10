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

output "worker_ecr_repository_url" {
  description = "ECR repository URL for the factory worker container image."
  value       = aws_ecr_repository.worker.repository_url
}

output "worker_image_uri_latest" {
  description = "Image URI for the latest factory worker image."
  value       = "${aws_ecr_repository.worker.repository_url}:latest"
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

output "ecs_cluster_name" {
  description = "ECS cluster where one-off Fargate worker tasks will run."
  value       = aws_ecs_cluster.factory.name
}

output "worker_execution_role_name" {
  description = "IAM role used by ECS/Fargate to pull the worker image and write container logs."
  value       = aws_iam_role.worker_execution.name
}

output "worker_task_role_name" {
  description = "IAM role used by worker code to update factory status in S3."
  value       = aws_iam_role.worker_task.name
}

output "worker_task_definition_family" {
  description = "ECS task definition family for one-off factory worker tasks."
  value       = aws_ecs_task_definition.worker.family
}

output "worker_task_definition_arn" {
  description = "Latest ECS task definition ARN for one-off factory worker tasks."
  value       = aws_ecs_task_definition.worker.arn
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
