# Software Factory Prototype

This project is a small demo of a software factory.

The idea is simple: a user describes a problem or change in plain English, and the system creates a pull request with the code change.

The demo app is a basic calculator. It can be deliberately broken, then repaired by the factory flow.

## What The Demo Shows

The prototype supports two ways to start factory work:

1. From the web UI: type a request such as `fix this error` and start the factory.
2. From GitHub Issues: create an issue and add the `factory` label.

In both cases, the system does the same thing:

```text
User request
  -> factory starts
  -> worker reads the code
  -> Codex makes the code change
  -> tests run
  -> branch is pushed
  -> pull request is created
```

## Example

A PM can create a GitHub issue like this:

```text
Title:
I'm getting a divisionbyzero error when trying out a divide operation

Description:
I tried doing 12/2 in the app but it blew up with a divisionbyzero error.
```

Then they add the `factory` label.

The GitHub workflow submits the issue to the factory, waits for the job to finish, and the worker creates a PR with the proposed fix.

## Main Pieces

- Django calculator app: the simple demo application.
- Factory API: receives requests from the UI or GitHub Actions.
- Factory worker: clones the repo, runs Codex, validates the code, and creates a PR.
- GitHub Actions: deploys images and lets GitHub issues trigger the factory.
- Terraform: creates the AWS resources.

## High-Level AWS Flow

The deployed version uses AWS like this:

```text
Django app on Lambda
  -> starts a Fargate worker task
  -> worker updates status in S3
  -> worker creates a GitHub pull request
```

S3 is used for the latest factory status. SSM Parameter Store is used for secrets such as the OpenAI API key and GitHub token.

The current prototype avoids always-on servers where possible. There is no API Gateway, load balancer, database, or always-running EC2 instance.

## Local Development

Create a virtual environment, install dependencies, and run the app:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python manage.py runserver
```

Open:

```text
http://127.0.0.1:8000
```

Run checks:

```bash
python manage.py check
python manage.py test
```

To let the local factory invoke Codex, install and authenticate the Codex CLI so `codex` is available on `PATH`.

## AWS Setup Summary

The detailed Terraform guide is in `infra/README.md`.

Short version:

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform apply
```

The first apply creates the base infrastructure and image repositories. After images are pushed, set `django_image_uri` in `terraform.tfvars` and apply again to create the Lambda Function URL.

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

Set it to the Lambda Function URL without any path at the end.

## Deployment

Pushing to `main` runs the image deployment workflow:

```text
.github/workflows/deploy-images.yml
```

That workflow builds and pushes the Django and worker images, then updates the Lambda function.

## GitHub Issue Flow

The issue workflow is here:

```text
.github/workflows/factory-issue.yml
```

To test it:

1. Create a GitHub issue.
2. Add a clear title and description.
3. Add the `factory` label.
4. Watch the `Factory Issue` workflow.
5. When it finishes, check the generated PR.

A green workflow means the factory job completed. A red workflow means the job failed or timed out.

## Teardown

Destroy AWS resources when the prototype is not needed:

```bash
terraform -chdir=infra destroy
```

## Current Limitations

- The prototype is designed for one factory job at a time.
- Status is stored as a single latest JSON file in S3.
- The worker creates PRs but does not yet comment back on the original issue.
- The public Lambda Function URL is unauthenticated for simplicity.
- The reset demo path is for demos only, not production rollback.
