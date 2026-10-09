import json
from datetime import datetime, timezone
from uuid import uuid4

import boto3
from botocore.exceptions import ClientError
from django.conf import settings


IDLE_STATUS = {
    "state": "idle",
    "task": "",
    "detail": "No factory run has started yet.",
}

UNKNOWN_JOB_STATUS = {
    "state": "unknown",
    "task": "",
    "detail": "No status was found for this factory run.",
}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def new_job_id():
    return str(uuid4())


def using_s3():
    return settings.FACTORY_STATUS_BACKEND == "s3"


def s3_client():
    return boto3.client("s3")


def read_status_payload():
    if using_s3():
        if not settings.FACTORY_STATUS_BUCKET:
            raise ValueError("FACTORY_STATUS_BUCKET is required when FACTORY_STATUS_BACKEND=s3.")

        try:
            response = s3_client().get_object(
                Bucket=settings.FACTORY_STATUS_BUCKET,
                Key=settings.FACTORY_STATUS_KEY,
            )
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"NoSuchKey", "404"}:
                return None
            raise

        return json.loads(response["Body"].read().decode("utf-8"))

    if not settings.FACTORY_STATUS_FILE.exists():
        return None

    return json.loads(settings.FACTORY_STATUS_FILE.read_text(encoding="utf-8"))


def read_status(job_id=None):
    status = read_status_payload()
    if status is None:
        return IDLE_STATUS.copy()

    if job_id is not None and status.get("job_id") != job_id:
        return None
    return status


def write_status(payload):
    status_json = json.dumps(payload, indent=2)

    if using_s3():
        if not settings.FACTORY_STATUS_BUCKET:
            raise ValueError("FACTORY_STATUS_BUCKET is required when FACTORY_STATUS_BACKEND=s3.")

        s3_client().put_object(
            Bucket=settings.FACTORY_STATUS_BUCKET,
            Key=settings.FACTORY_STATUS_KEY,
            Body=status_json.encode("utf-8"),
            ContentType="application/json",
        )
        return payload

    settings.FACTORY_STATUS_FILE.write_text(status_json, encoding="utf-8")
    return payload


def start_status(task, job_id=None):
    return write_status(
        {
            "job_id": job_id or new_job_id(),
            "state": "running",
            "task": task,
            "updated_at": now_iso(),
            "detail": "Local factory process started.",
        }
    )


def complete_status(job_id, payload):
    current = read_status()
    current_job_id = current.get("job_id")
    current_state = current.get("state")

    if current_job_id not in (job_id, None):
        print(
            f"[factory] ignored stale status update for job_id={job_id}; "
            f"current job_id={current_job_id}",
            flush=True,
        )
        return False

    if current_job_id is None and current_state not in (None, "idle"):
        print(
            f"[factory] ignored status update for job_id={job_id}; "
            f"current state={current_state}",
            flush=True,
        )
        return False

    next_status = {**payload, "job_id": job_id, "updated_at": now_iso()}
    write_status(next_status)
    return True


def clear_status():
    return write_status(
        {
            **IDLE_STATUS,
            "job_id": None,
            "updated_at": now_iso(),
        }
    )
