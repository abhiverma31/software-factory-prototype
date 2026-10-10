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


def main():
    try:
        job_id = required_env("JOB_ID")
        task = required_env("TASK_TEXT")
        repo_url = required_env("FACTORY_REPO_URL")
    except ValueError as exc:
        print(f"[worker] {exc}", flush=True)
        return 2

    workspace = Path(os.environ.get("FACTORY_WORKSPACE_DIR", "/tmp/software-factory-workspace"))

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

    file_count = count_workspace_files(workspace)
    complete_status(
        job_id,
        {
            "state": "completed",
            "task": task,
            "detail": f"Repository cloned successfully. Found {file_count} files.",
        },
    )
    print(f"[worker] cloned repository job_id={job_id} files={file_count}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
