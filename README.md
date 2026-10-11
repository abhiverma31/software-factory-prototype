# Software Factory Prototype

A Django prototype that demonstrates an agentic software factory loop:

1. A user or PM describes a change in plain English.
2. The app starts a factory worker.
3. The worker clones the repository, runs Codex against the request, validates the result, commits the change, pushes a branch, and opens a pull request.

The calculator app is intentionally small so the prototype can focus on the factory workflow rather than product complexity.

## What It Does

The app has a simple calculator UI with basic operations. The demo can intentionally fail on division, then a user can ask the factory to fix it from the UI.

There is also a GitHub issue entry point. A PM can create an issue, add the `factory` label, and GitHub Actions will submit that issue to the same factory API used by the UI.

Both paths converge on the same backend flow:

```text
UI button or GitHub issue
  -> Django Lambda /factory/fix/
  -> ECS RunTask
  -> Fargate worker
  -> Codex edits cloned repo
  -> Django checks/tests
  -> Git branch + commit + push
  -> GitHub pull request
```

## Entry Points

### Web UI

The browser calls:

```text
POST /factory/fix/
```

with JSON similar to:

```json
{
  "task": "fix this",
  "context": {
    "calculator": {
      "operation": "divide",
      "left": "12",
      "right": "2",
      "error": "ZeroDivisionError: float division by zero"
    }
  }
}
```

The browser then polls:

```text
GET /factory/status/?job_id=<job_id>
```

### GitHub Issue

The workflow `.github/workflows/factory-issue.yml` runs when an issue gets the `factory` label.

It sends the issue title and description to the same Lambda endpoint:

```json
{
  "task": "Issue title\n\nIssue description",
  "context": {
    "source": "github_issue",
    "issue_number": "...",
    "issue_title": "...",
    "issue_body": "...",
    "issue_url": "...",
    "issue_author": "..."
  }
}
```

The workflow waits for the factory job to finish by polling `/factory/status/`. A green workflow means the worker completed. A red workflow means the worker failed or timed out.

## Main Components

- `calculator/`: the demo calculator app.
- `factory/views.py`: API endpoints for starting factory work, reading status, and resetting the demo.
- `factory/runner.py`: starts either the local worker or an ECS/Fargate task.
- `factory/worker.py`: the worker entry point. It clones the repo, calls Codex, validates, commits, pushes, and creates a PR.
- `factory/status_store.py`: stores the latest factory status in a local file or S3.
- `software_factory/demo_reset.py`: resets the local demo back to the intentionally broken baseline.
- `Dockerfile`: Django Lambda image.
- `Dockerfile.worker`: factory worker image.
- `infra/`: Terraform for AWS resources.
- `.github/workflows/deploy-images.yml`: builds/pushes Django and worker images and updates Lambda.
- `.github/workflows/factory-issue.yml`: triggers the factory from GitHub issues.

## AWS Architecture

The deployed prototype uses mostly on-demand AWS services:

- Lambda Function URL for the Django app.
- ECS/Fargate `RunTask` for worker execution.
- ECR repositories for the Django and worker container images.
- S3 object `factory/status.json` for shared status between Lambda, worker, UI, and GitHub Actions.
- SSM SecureString parameters for GitHub and OpenAI secrets.
- CloudWatch log groups for Lambda and worker logs.
- GitHub Actions OIDC role for image deployment.

There is no API Gateway, NAT Gateway, ALB, RDS, or always-on EC2 instance in the current prototype.

## Local Development

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python manage.py test
python manage.py runserver
```

Open:

```text
http://127.0.0.1:8000
```

To let the local worker invoke Codex, install and authenticate the Codex CLI so `codex` is available on `PATH`.

Run checks:

```bash
python manage.py check
python manage.py test
```

## AWS Setup Summary

The detailed Terraform guide is in `infra/README.md`. The short version is:

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform apply
```

The first apply creates the base infrastructure and ECR repositories. After images are pushed, set `django_image_uri` in `terraform.tfvars` and apply again to create the Lambda Function URL.

Secrets are stored outside Terraform state:

```bash
aws ssm put-parameter \
  --name /software-factory/dev/openai-api-key \
  --type SecureString \
  --value "$OPENAI_API_KEY" \
  --overwrite

aws ssm put-parameter \
  --name /software-factory/dev/github-token \
  --type SecureString \
  --value "$GITHUB_TOKEN" \
  --overwrite
```

GitHub Actions also needs this repository secret:

```text
FACTORY_LAMBDA_URL
```

Set it to the Lambda Function URL without a trailing path, for example:

```text
https://<id>.lambda-url.us-east-1.on.aws
```

## Deployment

Pushing to `main` runs `.github/workflows/deploy-images.yml`.

That workflow:

1. Assumes the AWS deploy role through GitHub OIDC.
2. Builds and pushes the Django image.
3. Builds and pushes the worker image.
4. Updates the Lambda function to the new Django image.

Terraform owns the infrastructure. GitHub Actions owns routine image deployment.

## Testing The GitHub Issue Flow

1. Create a GitHub issue.
2. Use a concrete title and description, for example:

```text
Title:
I'm getting a divisionbyzero error when trying out a divide operation

Description:
I tried doing 12/2 in the app but it blew up with a divisionbyzero error.
```

3. Add the `factory` label.
4. Watch the `Factory Issue` workflow.
5. When it completes, check the PR created by the worker.

## Teardown

Destroy AWS resources when the prototype is not needed:

```bash
terraform -chdir=infra destroy
```

## Current Limitations

- The status store is a single S3 JSON object for the latest/current job.
- The worker creates PRs but does not yet comment back on the originating GitHub issue.
- The public Lambda Function URL is unauthenticated for prototype simplicity.
- The factory is designed for one prototype request at a time, not concurrent production traffic.
- The reset demo path is for local/demo behavior, not a production rollback mechanism.
