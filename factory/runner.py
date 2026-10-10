import subprocess
import sys

import boto3
from django.conf import settings

from .status_store import start_status


def start_local_factory(task, status):
    settings.FACTORY_RUNS_DIR.mkdir(exist_ok=True)

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


def start_ecs_factory(task, status):
    missing = [
        name
        for name, value in {
            "FACTORY_ECS_CLUSTER": settings.FACTORY_ECS_CLUSTER,
            "FACTORY_ECS_TASK_DEFINITION": settings.FACTORY_ECS_TASK_DEFINITION,
            "FACTORY_ECS_SUBNETS": settings.FACTORY_ECS_SUBNETS,
        }.items()
        if not value
    ]
    if missing:
        raise ValueError(f"{', '.join(missing)} must be configured for ECS factory runs.")

    print(f"[factory] starting ECS worker for task: {task}", flush=True)
    response = boto3.client("ecs").run_task(
        cluster=settings.FACTORY_ECS_CLUSTER,
        taskDefinition=settings.FACTORY_ECS_TASK_DEFINITION,
        launchType="FARGATE",
        networkConfiguration={
            "awsvpcConfiguration": {
                "subnets": settings.FACTORY_ECS_SUBNETS,
                "assignPublicIp": settings.FACTORY_ECS_ASSIGN_PUBLIC_IP,
            }
        },
        overrides={
            "containerOverrides": [
                {
                    "name": settings.FACTORY_WORKER_CONTAINER_NAME,
                    "environment": [
                        {"name": "JOB_ID", "value": status["job_id"]},
                        {"name": "TASK_TEXT", "value": task},
                    ],
                }
            ]
        },
    )
    failures = response.get("failures", [])
    if failures:
        raise RuntimeError(f"ECS RunTask failed: {failures}")
    return status


def start_factory(task):
    status = start_status(task)
    if settings.FACTORY_RUNNER_BACKEND == "ecs":
        return start_ecs_factory(task, status)
    return start_local_factory(task, status)
