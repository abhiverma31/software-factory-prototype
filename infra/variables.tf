variable "aws_region" {
  description = "AWS region for all prototype resources."
  type        = string
  default     = "us-east-1"
}

variable "aws_profile" {
  description = "Optional local AWS CLI profile name. Leave blank to use the default provider credential chain."
  type        = string
  default     = ""
}

variable "project_name" {
  description = "Short lowercase project name used in resource names."
  type        = string
  default     = "software-factory"

  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.project_name))
    error_message = "project_name must contain only lowercase letters, numbers, and hyphens."
  }
}

variable "environment" {
  description = "Environment name used in resource names."
  type        = string
  default     = "dev"

  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.environment))
    error_message = "environment must contain only lowercase letters, numbers, and hyphens."
  }
}

variable "log_retention_days" {
  description = "CloudWatch log retention. Keep low for the cost-minimal prototype."
  type        = number
  default     = 1
}
