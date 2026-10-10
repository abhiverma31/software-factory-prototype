import json
import os
import tempfile
from pathlib import Path

from django.conf import settings
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings
from django.urls import reverse

from .runner import start_factory
from . import worker
from .status_store import clear_status, complete_status, read_status, start_status, write_status


class IsolatedStatusFileMixin:
    def setUp(self):
        super().setUp()
        self.status_dir = tempfile.TemporaryDirectory()
        self.settings_override = override_settings(
            FACTORY_STATUS_FILE=Path(self.status_dir.name) / "factory_status.json"
        )
        self.settings_override.enable()

    def tearDown(self):
        self.settings_override.disable()
        self.status_dir.cleanup()
        super().tearDown()


class FactoryViewTests(IsolatedStatusFileMixin, TestCase):
    def test_factory_rejects_empty_task(self):
        response = self.client.post(
            reverse("factory-fix"),
            data=json.dumps({"task": ""}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_factory_rejects_malformed_json(self):
        response = self.client.post(
            reverse("factory-fix"),
            data="{not valid json",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    @patch("factory.views.start_factory")
    def test_factory_accepts_arbitrary_task_text(self, start_factory):
        start_factory.return_value = {
            "job_id": "job-1",
            "state": "running",
            "task": "fix whatever caused the calculator failure",
            "detail": "Local factory process started.",
        }
        response = self.client.post(
            reverse("factory-fix"),
            data=json.dumps({"task": "fix whatever caused the calculator failure"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["state"], "running")
        self.assertIn("calculator failure", response.json()["task"])

    def test_status_can_be_read_for_current_job(self):
        start_status("fix this error", job_id="job-1")

        response = self.client.get(reverse("factory-status"), {"job_id": "job-1"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["job_id"], "job-1")
        self.assertEqual(response.json()["state"], "running")

    def test_status_without_job_id_returns_idle(self):
        start_status("old completed job", job_id="old-job")
        complete_status("old-job", {"state": "completed", "task": "old completed job"})

        response = self.client.get(reverse("factory-status"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["state"], "idle")
        self.assertNotIn("job_id", response.json())

    def test_status_returns_unknown_for_missing_job(self):
        start_status("different job", job_id="job-2")

        response = self.client.get(reverse("factory-status"), {"job_id": "job-1"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["job_id"], "job-1")
        self.assertEqual(response.json()["state"], "unknown")


class FactoryStatusCopyTests(TestCase):
    def test_status_is_clear_when_codex_is_missing(self):
        # The local worker writes this state when Codex CLI is unavailable.
        self.assertIn("Codex CLI", "Codex CLI was not found on PATH.")


class FactoryRunnerTests(IsolatedStatusFileMixin, TestCase):
    @patch("factory.runner.subprocess.Popen")
    def test_local_runner_starts_local_agent(self, popen):
        status = start_factory("fix local thing")

        self.assertEqual(status["state"], "running")
        popen.assert_called_once()

    @override_settings(
        FACTORY_RUNNER_BACKEND="ecs",
        FACTORY_ECS_CLUSTER="cluster-name",
        FACTORY_ECS_TASK_DEFINITION="task-def-arn",
        FACTORY_ECS_SUBNETS=["subnet-1"],
        FACTORY_ECS_ASSIGN_PUBLIC_IP="ENABLED",
        FACTORY_WORKER_CONTAINER_NAME="worker",
    )
    @patch("factory.runner.boto3.client")
    def test_ecs_runner_starts_fargate_task(self, boto3_client):
        ecs = Mock()
        ecs.run_task.return_value = {"tasks": [{"taskArn": "task-arn"}], "failures": []}
        boto3_client.return_value = ecs

        status = start_factory("dummy fargate worker test")

        self.assertEqual(status["state"], "running")
        ecs.run_task.assert_called_once()
        call_kwargs = ecs.run_task.call_args.kwargs
        self.assertEqual(call_kwargs["cluster"], "cluster-name")
        self.assertEqual(call_kwargs["taskDefinition"], "task-def-arn")
        self.assertEqual(call_kwargs["networkConfiguration"]["awsvpcConfiguration"]["subnets"], ["subnet-1"])
        env = call_kwargs["overrides"]["containerOverrides"][0]["environment"]
        self.assertIn({"name": "JOB_ID", "value": status["job_id"]}, env)
        self.assertIn({"name": "TASK_TEXT", "value": "dummy fargate worker test"}, env)


class FactoryStatusStoreTests(IsolatedStatusFileMixin, TestCase):
    def test_status_backend_defaults_to_file(self):
        self.assertEqual(settings.FACTORY_STATUS_BACKEND, "file")

    def test_read_status_defaults_to_idle_when_missing(self):
        clear_status()

        self.assertEqual(read_status()["state"], "idle")

    def test_start_status_writes_job_id_and_running_state(self):
        status = start_status("fix this error", job_id="job-1")

        self.assertEqual(status["job_id"], "job-1")
        self.assertEqual(read_status("job-1")["state"], "running")

    def test_complete_status_ignores_stale_job(self):
        start_status("newer job", job_id="new-job")

        updated = complete_status("old-job", {"state": "completed", "task": "old"})

        self.assertFalse(updated)
        self.assertEqual(read_status()["job_id"], "new-job")
        self.assertEqual(read_status()["state"], "running")

    def test_complete_status_recovers_when_status_was_reset_to_idle(self):
        clear_status()

        updated = complete_status("job-1", {"state": "completed", "task": "fix this error"})

        self.assertTrue(updated)
        self.assertEqual(read_status()["job_id"], "job-1")
        self.assertEqual(read_status()["state"], "completed")

    def test_complete_status_updates_matching_job(self):
        start_status("fix this error", job_id="job-1")

        updated = complete_status("job-1", {"state": "completed", "task": "fix this error"})

        self.assertTrue(updated)
        self.assertEqual(read_status()["state"], "completed")

    def test_clear_status_writes_idle_state(self):
        start_status("fix this error", job_id="job-1")
        clear_status()

        self.assertTrue(settings.FACTORY_STATUS_FILE.exists())
        self.assertEqual(read_status()["state"], "idle")
        self.assertIsNone(read_status()["job_id"])


class FactoryS3StatusStoreTests(TestCase):
    @override_settings(
        FACTORY_STATUS_BACKEND="s3",
        FACTORY_STATUS_BUCKET="status-bucket",
        FACTORY_STATUS_KEY="factory/status.json",
    )
    @patch("factory.status_store.s3_client")
    def test_write_status_puts_json_in_s3(self, s3_client):
        client = Mock()
        s3_client.return_value = client

        write_status({"state": "running", "job_id": "job-1"})

        client.put_object.assert_called_once_with(
            Bucket="status-bucket",
            Key="factory/status.json",
            Body=json.dumps({"state": "running", "job_id": "job-1"}, indent=2).encode("utf-8"),
            ContentType="application/json",
        )

    @override_settings(
        FACTORY_STATUS_BACKEND="s3",
        FACTORY_STATUS_BUCKET="status-bucket",
        FACTORY_STATUS_KEY="factory/status.json",
    )
    @patch("factory.status_store.s3_client")
    def test_read_status_reads_json_from_s3(self, s3_client):
        body = Mock()
        body.read.return_value = b'{"state": "completed", "job_id": "job-1"}'
        client = Mock()
        client.get_object.return_value = {"Body": body}
        s3_client.return_value = client

        self.assertEqual(read_status("job-1")["state"], "completed")
        client.get_object.assert_called_once_with(Bucket="status-bucket", Key="factory/status.json")


class FactoryWorkerTests(IsolatedStatusFileMixin, TestCase):
    @patch("factory.worker.subprocess.run")
    def test_clone_repository_uses_shallow_git_clone(self, run):
        worker.clone_repository("https://github.com/example/repo.git", Path("/tmp/workspace"))

        run.assert_called_once_with(
            ["git", "clone", "--depth", "1", "https://github.com/example/repo.git", "/tmp/workspace"],
            check=True,
            capture_output=True,
            text=True,
        )

    def test_count_workspace_files_ignores_git_metadata(self):
        workspace = Path(self.status_dir.name) / "workspace"
        (workspace / "factory").mkdir(parents=True)
        (workspace / "factory" / "worker.py").write_text("print('worker')", encoding="utf-8")
        (workspace / ".git" / "objects").mkdir(parents=True)
        (workspace / ".git" / "objects" / "ignored").write_text("metadata", encoding="utf-8")

        self.assertEqual(worker.count_workspace_files(workspace), 1)

    @patch("factory.worker.count_workspace_files", return_value=42)
    @patch("factory.worker.clone_repository")
    def test_worker_clones_repo_and_completes_job_from_environment(self, clone_repository, count_workspace_files):
        start_status("clone repo test", job_id="test-job-1")

        with patch.dict(
            os.environ,
            {
                "JOB_ID": "test-job-1",
                "TASK_TEXT": "clone repo test",
                "FACTORY_REPO_URL": "https://github.com/abhiverma31/software-factory-prototype.git",
                "FACTORY_WORKSPACE_DIR": "/tmp/test-workspace",
            },
        ):
            exit_code = worker.main()

        status = read_status("test-job-1")
        self.assertEqual(exit_code, 0)
        clone_repository.assert_called_once_with(
            "https://github.com/abhiverma31/software-factory-prototype.git",
            Path("/tmp/test-workspace"),
        )
        count_workspace_files.assert_called_once_with(Path("/tmp/test-workspace"))
        self.assertEqual(status["state"], "completed")
        self.assertEqual(status["task"], "clone repo test")
        self.assertEqual(status["detail"], "Repository cloned successfully. Found 42 files.")

    def test_worker_requires_job_id_task_text_and_repo_url(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(worker.main(), 2)
