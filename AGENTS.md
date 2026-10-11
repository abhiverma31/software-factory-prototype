# Software Factory Agent Notes

This repo is a Django-based software factory prototype. Keep changes simple, focused, and easy to explain.

## Project Shape

- `calculator/`: demo calculator app.
- `factory/`: factory API, runner, status store, local agent, and worker code.
- `software_factory/`: Django settings and demo reset helpers.
- `infra/`: Terraform for AWS resources.
- `.github/workflows/deploy-images.yml`: builds and deploys Django/worker images.
- `.github/workflows/factory-issue.yml`: starts factory work from GitHub issues labeled `factory`.

## Main Flow

```text
UI or GitHub issue
  -> Django /factory/fix/
  -> ECS RunTask
  -> Fargate worker
  -> clone repo
  -> Codex edits code
  -> Django checks/tests
  -> commit + push branch
  -> GitHub PR
```

## Local Commands

Use the project virtualenv when available:

```bash
.venv/bin/python manage.py check
.venv/bin/python manage.py test
.venv/bin/python manage.py runserver
```

## AWS And Secrets

Do not commit secrets. Do not put secret values in Terraform state.

Expected SSM SecureString parameters:

```text
/software-factory/dev/openai-api-key
/software-factory/dev/github-token
```

GitHub repository secret:

```text
FACTORY_LAMBDA_URL
```

Factory status is stored in S3 at:

```text
factory/status.json
```

## Terraform

Terraform lives in `infra/`.

Prefer letting the user run AWS-changing Terraform commands unless they explicitly ask the agent to run them.

```bash
terraform -chdir=infra plan
terraform -chdir=infra apply
terraform -chdir=infra destroy
```

## GitHub Actions

`deploy-images.yml` should not run for README-only, AGENTS.md-only, or workflow-only changes.

`factory-issue.yml` polls `/factory/status/?job_id=...` so a green issue workflow means the factory job completed.

## Coding Guidelines

- Prefer small, incremental changes.
- Keep README language simple enough for a common audience.
- Update tests when factory behavior changes.
- Avoid hardcoding task-specific behavior such as division-only PR titles.
- Keep UI status messages short and human-readable.
- Preserve local demo reset behavior unless intentionally changing the demo flow.
