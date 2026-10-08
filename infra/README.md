# Software Factory Infrastructure

Terraform for the cost-minimal AWS prototype.

## Step 1 resources

This first step creates only:

- Private S3 bucket for `factory/status.json`
- CloudWatch log group for Django Lambda with 1-day retention
- CloudWatch log group for factory worker with 1-day retention
- Output names for OpenAI and GitHub SSM SecureString parameters

No Lambda, Fargate, API Gateway, NAT Gateway, ALB, RDS, or always-on compute is created yet.

## Commands

```bash
cd /Users/abhishekverma/software-factory/infra
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform plan
terraform apply
terraform destroy
```

If using a personal AWS profile, set it in `terraform.tfvars`:

```hcl
aws_profile = "personal"
aws_region  = "us-east-1"
```

## Secrets

Do not put secret values in Terraform state. After apply, create these manually:

```bash
aws ssm put-parameter --name /software-factory/dev/openai-api-key --type SecureString --value "$OPENAI_API_KEY" --overwrite

aws ssm put-parameter --name /software-factory/dev/github-token --type SecureString --value "$GITHUB_TOKEN" --overwrite
```
