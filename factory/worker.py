import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib import request
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse, urlunparse

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "software_factory.settings")

import boto3
import django
from django.apps import apps

if not apps.ready:
    django.setup()

from .status_store import complete_status


def required_env(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required.")
    return value


def clone_repository(repo_url, workspace):
    if workspace.exists():
        shutil.rmtree(workspace)

    subprocess.run(
        ["git", "clone", "--depth", "1", repo_url, str(workspace)],
        check=True,
        capture_output=True,
        text=True,
    )


def ssm_client():
    return boto3.client("ssm")


def load_github_token():
    parameter_name = required_env("GITHUB_TOKEN_PARAMETER_NAME")
    response = ssm_client().get_parameter(Name=parameter_name, WithDecryption=True)
    return response["Parameter"]["Value"]


def load_openai_api_key():
    parameter_name = required_env("OPENAI_API_KEY_PARAMETER_NAME")
    response = ssm_client().get_parameter(Name=parameter_name, WithDecryption=True)
    return response["Parameter"]["Value"].strip()


def authenticated_repo_url(repo_url, token):
    parsed = urlparse(repo_url)
    token_user = "x-access-token"
    token_password = quote(token, safe="")
    return urlunparse(parsed._replace(netloc=f"{token_user}:{token_password}@{parsed.netloc}"))


def count_workspace_files(workspace):
    return sum(1 for path in workspace.rglob("*") if path.is_file() and ".git" not in path.parts)


def load_task_context():
    raw_context = os.environ.get("TASK_CONTEXT", "").strip()
    if not raw_context:
        return {}
    try:
        return json.loads(raw_context)
    except json.JSONDecodeError:
        return {"raw": raw_context}


def format_calculator_context(context):
    calculator = context.get("calculator") if isinstance(context, dict) else None
    if not isinstance(calculator, dict):
        return "No calculator context was provided."

    operation = calculator.get("operation") or "unknown"
    left = calculator.get("left") or ""
    right = calculator.get("right") or ""
    error = calculator.get("error")
    result = calculator.get("result")

    if error:
        return f'Calculator operation "{operation}" failed for left={left}, right={right}. Error: {error}.'
    return f'Calculator operation "{operation}" ran for left={left}, right={right}. Result: {result}.'


def build_codex_prompt(task, context):
    return "\n".join(
        [
            "User request:",
            task,
            "",
            "Observed application context:",
            format_calculator_context(context),
            "",
            "Repository task:",
            "Inspect the Django calculator code, fix the issue minimally, and preserve existing behavior.",
            "After editing, run the relevant checks or tests.",
        ]
    )


def prompt_preview(prompt, limit=1000):
    if len(prompt) <= limit:
        return prompt
    return f"{prompt[:limit]}..."


def factory_branch_name(job_id):
    safe_job_id = "".join(character if character.isalnum() or character in "-_" else "-" for character in job_id)
    return f"factory/{safe_job_id[:12]}"


def configure_git_author(workspace):
    author_name = os.environ.get("FACTORY_GIT_AUTHOR_NAME", "Software Factory")
    author_email = os.environ.get("FACTORY_GIT_AUTHOR_EMAIL", "software-factory@example.local")
    subprocess.run(["git", "config", "user.name", author_name], cwd=workspace, check=True)
    subprocess.run(["git", "config", "user.email", author_email], cwd=workspace, check=True)


def create_factory_branch(workspace, branch_name):
    configure_git_author(workspace)
    subprocess.run(["git", "checkout", "-b", branch_name], cwd=workspace, check=True)


def run_codex(workspace, prompt, openai_api_key):
    codex = shutil.which("codex")
    if not codex:
        raise RuntimeError("Codex CLI was not found in the worker image.")

    env = {**os.environ, "OPENAI_API_KEY": openai_api_key, "CODEX_API_KEY": openai_api_key}
    result = subprocess.run(
        [
            codex,
            "exec",
            "--skip-git-repo-check",
            "--approve-for-me",
            prompt,
        ],
        cwd=workspace,
        check=False,
        capture_output=True,
        text=True,
        timeout=int(os.environ.get("CODEX_TIMEOUT_SECONDS", "300")),
        env=env,
    )
    return result


def changed_files(workspace):
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=workspace,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line[3:] for line in result.stdout.splitlines() if line.strip()]


def run_validation(workspace):
    checks = [
        [sys.executable, "manage.py", "check"],
        [sys.executable, "manage.py", "test"],
    ]
    output = []
    for command in checks:
        result = subprocess.run(command, cwd=workspace, check=False, capture_output=True, text=True)
        output.append(f"$ {' '.join(command)}\n{result.stdout}{result.stderr}")
        if result.returncode != 0:
            return result.returncode, "\n".join(output)
    return 0, "\n".join(output)


def commit_factory_changes(workspace, branch_name, task):
    subprocess.run(["git", "add", "."], cwd=workspace, check=True)
    subprocess.run(["git", "commit", "-m", f"Factory fix: {task[:80]}"], cwd=workspace, check=True)
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=workspace,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def push_factory_branch(workspace, repo_url, branch_name, token):
    push_url = authenticated_repo_url(repo_url, token)
    subprocess.run(["git", "remote", "set-url", "origin", push_url], cwd=workspace, check=True)
    try:
        subprocess.run(["git", "push", "origin", branch_name], cwd=workspace, check=True)
    finally:
        subprocess.run(["git", "remote", "set-url", "origin", repo_url], cwd=workspace, check=True)


def parse_github_repo(repo_url):
    parsed = urlparse(repo_url)
    repo_path = parsed.path.strip("/")
    if repo_path.endswith(".git"):
        repo_path = repo_path[:-4]

    parts = repo_path.split("/")
    if len(parts) != 2 or parsed.netloc != "github.com":
        raise ValueError("FACTORY_REPO_URL must be a GitHub HTTPS repo URL.")
    return parts[0], parts[1]


def create_pull_request(repo_url, branch_name, task, token):
    owner, repo = parse_github_repo(repo_url)
    body = json.dumps(
        {
            "title": f"Factory fix: {task[:80]}",
            "head": branch_name,
            "base": "main",
            "body": (
                "Created by the software factory prototype.\n\n"
                f"User request:\n{task}\n"
            ),
        }
    ).encode("utf-8")
    pr_request = request.Request(
        f"https://api.github.com/repos/{owner}/{repo}/pulls",
        data=body,
        method="POST",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "software-factory-prototype",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with request.urlopen(pr_request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return {
        "url": payload["html_url"],
        "number": payload["number"],
    }


def main():
    try:
        job_id = required_env("JOB_ID")
        task = required_env("TASK_TEXT")
        repo_url = required_env("FACTORY_REPO_URL")
    except ValueError as exc:
        print(f"[worker] {exc}", flush=True)
        return 2

    workspace = Path(os.environ.get("FACTORY_WORKSPACE_DIR", "/tmp/software-factory-workspace"))
    task_context = load_task_context()
    codex_prompt = build_codex_prompt(task, task_context)

    complete_status(
        job_id,
        {
            "state": "running",
            "task": task,
            "detail": "Cloning repository.",
        },
    )

    try:
        clone_repository(repo_url, workspace)
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or exc.stdout.strip() or "Repository clone failed."
        complete_status(
            job_id,
            {
                "state": "failed",
                "task": task,
                "detail": detail,
            },
        )
        print(f"[worker] clone failed job_id={job_id}: {detail}", flush=True)
        return 1

    branch_name = factory_branch_name(job_id)

    try:
        create_factory_branch(workspace, branch_name)
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() if exc.stderr else "Factory commit failed."
        complete_status(
            job_id,
            {
                "state": "failed",
                "task": task,
                "detail": detail,
                "prompt_preview": prompt_preview(codex_prompt),
            },
        )
        print(f"[worker] branch creation failed job_id={job_id}: {detail}", flush=True)
        return 1

    try:
        openai_api_key = load_openai_api_key()
        codex_result = run_codex(workspace, codex_prompt, openai_api_key)
    except (ValueError, KeyError, OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        complete_status(
            job_id,
            {
                "state": "failed",
                "task": task,
                "detail": f"Codex could not run: {exc}",
                "branch_name": branch_name,
                "openai_key_length": len(openai_api_key) if "openai_api_key" in locals() else 0,
                "prompt_preview": prompt_preview(codex_prompt),
            },
        )
        print(f"[worker] Codex failed to start job_id={job_id}: {exc.__class__.__name__}", flush=True)
        return 1

    codex_output = f"{codex_result.stdout}{codex_result.stderr}"
    if codex_result.returncode != 0:
        complete_status(
            job_id,
            {
                "state": "failed",
                "task": task,
                "detail": "Codex run failed.",
                "branch_name": branch_name,
                "codex_return_code": codex_result.returncode,
                "openai_key_length": len(openai_api_key),
                "codex_output": codex_output[-4000:],
                "prompt_preview": prompt_preview(codex_prompt),
            },
        )
        print(f"[worker] Codex failed job_id={job_id} return_code={codex_result.returncode}", flush=True)
        return 1

    try:
        files_changed = changed_files(workspace)
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() if exc.stderr else "Could not inspect Codex changes."
        complete_status(
            job_id,
            {
                "state": "failed",
                "task": task,
                "detail": detail,
                "branch_name": branch_name,
                "prompt_preview": prompt_preview(codex_prompt),
            },
        )
        print(f"[worker] git status failed job_id={job_id}: {detail}", flush=True)
        return 1

    if not files_changed:
        complete_status(
            job_id,
            {
                "state": "failed",
                "task": task,
                "detail": "Codex completed but did not modify any files.",
                "branch_name": branch_name,
                "prompt_preview": prompt_preview(codex_prompt),
            },
        )
        print(f"[worker] Codex made no changes job_id={job_id}", flush=True)
        return 1

    validation_return_code, validation_output = run_validation(workspace)
    if validation_return_code != 0:
        complete_status(
            job_id,
            {
                "state": "failed",
                "task": task,
                "detail": "Validation failed after Codex changes.",
                "branch_name": branch_name,
                "changed_files": files_changed,
                "validation_output": validation_output[-4000:],
                "prompt_preview": prompt_preview(codex_prompt),
            },
        )
        print(f"[worker] validation failed job_id={job_id}", flush=True)
        return 1

    try:
        commit_sha = commit_factory_changes(workspace, branch_name, task)
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() if exc.stderr else "Factory commit failed."
        complete_status(
            job_id,
            {
                "state": "failed",
                "task": task,
                "detail": detail,
                "branch_name": branch_name,
                "changed_files": files_changed,
                "prompt_preview": prompt_preview(codex_prompt),
            },
        )
        print(f"[worker] commit failed job_id={job_id}: {detail}", flush=True)
        return 1

    try:
        github_token = load_github_token()
        push_factory_branch(workspace, repo_url, branch_name, github_token)
    except (ValueError, KeyError, subprocess.CalledProcessError) as exc:
        complete_status(
            job_id,
            {
                "state": "failed",
                "task": task,
                "detail": "Factory commit was created locally, but pushing the branch to GitHub failed.",
                "branch_name": branch_name,
                "commit_sha": commit_sha,
                "prompt_preview": prompt_preview(codex_prompt),
            },
        )
        print(f"[worker] push failed job_id={job_id}: {exc.__class__.__name__}", flush=True)
        return 1

    try:
        pull_request = create_pull_request(repo_url, branch_name, task, github_token)
    except (ValueError, KeyError, HTTPError, URLError) as exc:
        complete_status(
            job_id,
            {
                "state": "failed",
                "task": task,
                "detail": "Factory branch was pushed to GitHub, but creating the pull request failed.",
                "branch_name": branch_name,
                "commit_sha": commit_sha,
                "pushed_branch": True,
                "prompt_preview": prompt_preview(codex_prompt),
            },
        )
        print(f"[worker] PR creation failed job_id={job_id}: {exc.__class__.__name__}", flush=True)
        return 1

    complete_status(
        job_id,
        {
            "state": "completed",
            "task": task,
            "detail": (
                "Repository cloned successfully. "
                f"Codex changed {len(files_changed)} file(s), validation passed, and a factory pull request was created."
            ),
            "branch_name": branch_name,
            "commit_sha": commit_sha,
            "changed_files": files_changed,
            "pushed_branch": True,
            "pull_request_url": pull_request["url"],
            "pull_request_number": pull_request["number"],
            "prompt_preview": prompt_preview(codex_prompt),
        },
    )
    print(
        (
            f"[worker] committed repository job_id={job_id} branch={branch_name} "
            f"commit={commit_sha} changed_files={len(files_changed)}"
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
