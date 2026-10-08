data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

locals {
  name_prefix = "${var.project_name}-${var.environment}"

  status_bucket_name = "${local.name_prefix}-status-${data.aws_caller_identity.current.account_id}-${var.aws_region}"

  openai_api_key_parameter_name = "/${var.project_name}/${var.environment}/openai-api-key"
  github_token_parameter_name   = "/${var.project_name}/${var.environment}/github-token"

  tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
    Prototype   = "true"
  }
}
