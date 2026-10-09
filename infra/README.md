# Software Factory Infrastructure

Terraform for the cost-minimal AWS prototype.

## Resources

This stack creates:

- Private S3 bucket for `factory/status.json`
- CloudWatch log group for Django Lambda with 1-day retention
- CloudWatch log group for factory worker with 1-day retention
- ECR repository for the Django Lambda image
- Optional Django Lambda + public Lambda Function URL once an image URI is supplied
- Output names for OpenAI and GitHub SSM SecureString parameters

No Fargate, API Gateway, NAT Gateway, ALB, RDS, or always-on compute is created yet.

## Deploy Django UI to Lambda

```bash
cd /Users/abhishekverma/software-factory/infra
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform apply
```

If using a personal AWS profile, set it in `terraform.tfvars`:

```hcl
aws_profile = "personal"
aws_region  = "us-east-1"
```

The first apply creates the ECR repository. Then build and push a Lambda-compatible image:

```bash
cd /Users/abhishekverma/software-factory
AWS_REGION=$(terraform -chdir=infra output -raw aws_region 2>/dev/null || echo us-east-1)
ECR_REPO=$(terraform -chdir=infra output -raw django_ecr_repository_url)
ECR_REGISTRY="${ECR_REPO%/*}"
aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$ECR_REGISTRY"
docker buildx build --platform linux/amd64 --provenance=false -t "$ECR_REPO:latest" --push .
```

Set the pushed image URI in `infra/terraform.tfvars`:

```hcl
django_image_uri = "<django_ecr_repository_url>:latest"
```

Then apply again:

```bash
terraform -chdir=/Users/abhishekverma/software-factory/infra apply
terraform -chdir=/Users/abhishekverma/software-factory/infra output -raw django_function_url
```

Open the printed Function URL in a browser. Destroy everything when done:

```bash
terraform -chdir=/Users/abhishekverma/software-factory/infra destroy
```

## Secrets

Do not put secret values in Terraform state. After apply, create these manually:

```bash
aws ssm put-parameter --name /software-factory/dev/openai-api-key --type SecureString --value "$OPENAI_API_KEY" --overwrite

aws ssm put-parameter --name /software-factory/dev/github-token --type SecureString --value "$GITHUB_TOKEN" --overwrite
```
