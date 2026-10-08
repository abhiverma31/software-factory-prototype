import subprocess
import sys

from django.conf import settings

from .status_store import start_status


def start_factory(task):
    settings.FACTORY_RUNS_DIR.mkdir(exist_ok=True)
    status = start_status(task)

    print(f"[factory] starting local agent for task: {task}", flush=True)
    subprocess.Popen(
        [
            sys.executable,
            "-m",
            "factory.local_agent",
            "--task",
            task,
            "--job-id",
            status["job_id"],
            "--repo",
            str(settings.BASE_DIR),
        ],
        cwd=settings.BASE_DIR,
    )
    return status
