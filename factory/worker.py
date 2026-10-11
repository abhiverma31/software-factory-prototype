import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "software_factory.settings")

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


def write_factory_marker(workspace, job_id, task, prompt):
    marker = workspace / "factory_run.txt"
    marker.write_text(f"Job ID: {job_id}\nTask: {task}\n\nPrepared Codex prompt:\n{prompt}\n", encoding="utf-8")
    return marker


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

    before_count = count_workspace_files(workspace)
    marker = write_factory_marker(workspace, job_id, task, codex_prompt)
    after_count = count_workspace_files(workspace)
    complete_status(
        job_id,
        {
            "state": "completed",
            "task": task,
            "detail": (
                "Repository cloned successfully. "
                f"File count changed from {before_count} to {after_count} after writing {marker.name}. "
                "Prepared Codex prompt with request context."
            ),
            "prompt_preview": prompt_preview(codex_prompt),
        },
    )
    print(
        f"[worker] cloned repository job_id={job_id} files_before={before_count} files_after={after_count}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
