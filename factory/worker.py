import os
import sys

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


def main():
    try:
        job_id = required_env("JOB_ID")
        task = required_env("TASK_TEXT")
    except ValueError as exc:
        print(f"[worker] {exc}", flush=True)
        return 2

    complete_status(
        job_id,
        {
            "state": "completed",
            "task": task,
            "detail": "Dummy worker completed.",
        },
    )
    print(f"[worker] completed dummy job_id={job_id}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
