import argparse
import shutil
import subprocess
import os
import sys
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "software_factory.settings")

import django

django.setup()

from .status_store import complete_status, now_iso


def log(message):
    print(f"[factory] {message}", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--repo", required=True)
    args = parser.parse_args()

    repo = Path(args.repo)
    local_codex = repo / "node_modules" / ".bin" / "codex"
    codex = str(local_codex) if local_codex.exists() else shutil.which("codex")
    now = now_iso()

    log(f"received task: {args.task}")
    log(f"working directory: {repo}")

    if not codex:
        log("Codex CLI not found")
        complete_status(
            args.job_id,
            {
                "state": "waiting_for_codex",
                "task": args.task,
                "updated_at": now,
                "detail": "Codex CLI was not found. Run npm install --save-dev @openai/codex, authenticate Codex, then click Start local factory again.",
            },
        )
        return 0

    prompt = (
        "You are operating a local software factory prototype.\n"
        "Use the user's task as the maintenance request.\n"
        "Work only in this repository.\n"
        "Keep the change small, run .venv/bin/python manage.py test, and stop when tests pass.\n\n"
        f"User task:\n{args.task}\n"
    )

    command = [
        codex,
        "exec",
        "--skip-git-repo-check",
        "--approve-for-me",
        prompt,
    ]
    log("launching Codex agent")

    output = []
    try:
        process = subprocess.Popen(
            command,
            cwd=repo,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        try:
            for line in process.stdout or []:
                output.append(line)
                sys.stdout.write(f"[codex] {line}")
                sys.stdout.flush()
            return_code = process.wait(timeout=180)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            log("Codex timed out after 180 seconds")
            complete_status(
                args.job_id,
                {
                    "state": "failed",
                    "task": args.task,
                    "detail": "Codex timed out after 180 seconds.",
                    "stdout": "".join(output)[-4000:],
                    "stderr": "",
                },
            )
            return 124
    except OSError as exc:
        log(f"failed to start Codex: {exc}")
        complete_status(
            args.job_id,
            {
                "state": "failed",
                "task": args.task,
                "detail": f"Failed to start Codex: {exc}",
                "stdout": "",
                "stderr": str(exc),
            },
        )
        return 1

    combined_output = "".join(output)
    state = "completed" if return_code == 0 else "failed"
    detail = "Codex run completed." if return_code == 0 else "Codex run failed. Check terminal output."
    log(f"Codex finished with state={state}, return_code={return_code}")

    complete_status(
        args.job_id,
        {
            "state": state,
            "task": args.task,
            "return_code": return_code,
            "detail": detail,
            "stdout": combined_output[-4000:],
            "stderr": "",
        },
    )
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
