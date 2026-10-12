# Factory Architecture

This diagram shows the current end-to-end software factory flow.

```mermaid
flowchart TD
    A[User or PM] --> B{Entry Point}

    B --> C[Web UI]
    B --> D[GitHub Issue<br/>factory label]

    D --> E[GitHub Actions]
    E -->|start job and poll status| F[AWS Lambda<br/>Django Factory API]
    C -->|start job and poll status| F

    F -->|write/read status| G[(S3<br/>Factory Status)]
    F -->|start worker| H[ECS RunTask]
    H --> I[Fargate Worker]

    I --> J[SSM Parameter Store<br/>Secrets]
    I --> K[GitHub Repo<br/>Clone Code]
    I --> L[OpenAI / Codex<br/>Generate Fix]
    L --> I

    I --> M[Run Checks and Tests]
    M --> N[Commit and Push Branch]
    N --> O[Create Pull Request]

    I -->|update status| G
```

## Flow Summary

1. A user starts from the web UI, or a PM creates a GitHub issue and adds the `factory` label.
2. The request reaches the Django factory API running on AWS Lambda.
3. Lambda writes initial status to S3 and starts an ECS Fargate worker task.
4. The worker reads secrets from SSM Parameter Store, clones the GitHub repo, and asks Codex to make the change.
5. The worker runs checks and tests.
6. If validation passes, the worker commits the change, pushes a branch, and creates a pull request.
7. S3 stores the latest job status so the UI and GitHub Actions workflow can track progress.
