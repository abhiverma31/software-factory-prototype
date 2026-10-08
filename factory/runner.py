import json
import subprocess
import sys
from datetime import datetime, timezone

from django.conf import settings


def read_status():
    if not settings.FACTORY_STATUS_FILE.exists():
        return {"state": "idle", "task": "", "detail": "No factory run has started yet."}

    return json.loads(settings.FACTORY_STATUS_FILE.read_text(encoding="utf-8"))


def start_factory(task):
    settings.FACTORY_RUNS_DIR.mkdir(exist_ok=True)
    status = {
        "state": "running",
        "task": task,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "detail": "Local factory process started.",
    }
    settings.FACTORY_STATUS_FILE.write_text(json.dumps(status, indent=2), encoding="utf-8")

    print(f"[factory] starting local agent for task: {task}", flush=True)
    subprocess.Popen(
        [
            sys.executable,
            "-m",
            "factory.local_agent",
            "--task",
            task,
            "--status-file",
            str(settings.FACTORY_STATUS_FILE),
            "--repo",
            str(settings.BASE_DIR),
        ],
        cwd=settings.BASE_DIR,
    )
    return status

