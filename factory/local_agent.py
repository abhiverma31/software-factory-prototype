import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def log(message):
    print(f"[factory] {message}", flush=True)


def write_status(path, payload):
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--status-file", required=True)
    parser.add_argument("--repo", required=True)
    args = parser.parse_args()

    status_file = Path(args.status_file)
    repo = Path(args.repo)
    local_codex = repo / "node_modules" / ".bin" / "codex"
    codex = str(local_codex) if local_codex.exists() else shutil.which("codex")
    now = datetime.now(timezone.utc).isoformat()

    log(f"received task: {args.task}")
    log(f"working directory: {repo}")

    if not codex:
        log("Codex CLI not found")
        write_status(
            status_file,
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
            write_status(
                status_file,
                {
                    "state": "failed",
                    "task": args.task,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "detail": "Codex timed out after 180 seconds.",
                    "stdout": "".join(output)[-4000:],
                    "stderr": "",
                },
            )
            return 124
    except OSError as exc:
        log(f"failed to start Codex: {exc}")
        write_status(
            status_file,
            {
                "state": "failed",
                "task": args.task,
                "updated_at": datetime.now(timezone.utc).isoformat(),
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

    write_status(
        status_file,
        {
            "state": state,
            "task": args.task,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "return_code": return_code,
            "detail": detail,
            "stdout": combined_output[-4000:],
            "stderr": "",
        },
    )
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
