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

    @patch("factory.views.start_factory")
    def test_factory_passes_context_to_runner(self, start_factory):
        start_factory.return_value = {
            "job_id": "job-1",
            "state": "running",
            "task": "fix this",
            "detail": "Factory worker started.",
        }
        context = {
            "calculator": {
                "left": "84",
                "right": "2",
                "operation": "divide",
                "error": "ZeroDivisionError: division by zero",
            }
        }

        response = self.client.post(
            reverse("factory-fix"),
            data=json.dumps({"task": "fix this", "context": context}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 202)
        start_factory.assert_called_once_with("fix this", context)

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

        context = {"calculator": {"operation": "divide", "error": "ZeroDivisionError: division by zero"}}

        status = start_factory("dummy fargate worker test", context)

        self.assertEqual(status["state"], "running")
        ecs.run_task.assert_called_once()
        call_kwargs = ecs.run_task.call_args.kwargs
        self.assertEqual(call_kwargs["cluster"], "cluster-name")
        self.assertEqual(call_kwargs["taskDefinition"], "task-def-arn")
        self.assertEqual(call_kwargs["networkConfiguration"]["awsvpcConfiguration"]["subnets"], ["subnet-1"])
        env = call_kwargs["overrides"]["containerOverrides"][0]["environment"]
        self.assertIn({"name": "JOB_ID", "value": status["job_id"]}, env)
        self.assertIn({"name": "TASK_TEXT", "value": "dummy fargate worker test"}, env)
        self.assertIn({"name": "TASK_CONTEXT", "value": json.dumps(context)}, env)


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

    def test_write_factory_marker_adds_workspace_file(self):
        workspace = Path(self.status_dir.name) / "workspace"
        workspace.mkdir()

        prompt = "User request:\nclone"
        marker = worker.write_factory_marker(workspace, "job-1", "clone", prompt)

        self.assertEqual(marker.name, "factory_run.txt")
        marker_text = marker.read_text(encoding="utf-8")
        self.assertIn("Job ID: job-1", marker_text)
        self.assertIn("Task: clone", marker_text)
        self.assertIn(prompt, marker_text)

    def test_build_codex_prompt_includes_calculator_error_context(self):
        prompt = worker.build_codex_prompt(
            "fix this",
            {
                "calculator": {
                    "left": "84",
                    "right": "2",
                    "operation": "divide",
                    "error": "ZeroDivisionError: division by zero",
                }
            },
        )

        self.assertIn("User request:\nfix this", prompt)
        self.assertIn('Calculator operation "divide" failed for left=84, right=2.', prompt)
        self.assertIn("ZeroDivisionError: division by zero", prompt)

    def test_prompt_preview_truncates_long_prompt(self):
        self.assertEqual(worker.prompt_preview("short", limit=10), "short")
        self.assertEqual(worker.prompt_preview("12345678901", limit=10), "1234567890...")

    def test_factory_branch_name_uses_short_safe_job_id(self):
        self.assertEqual(worker.factory_branch_name("9955717a-efdc-419c"), "factory/9955717a-efd")
        self.assertEqual(worker.factory_branch_name("job/id with spaces"), "factory/job-id-with-")

    def test_authenticated_repo_url_injects_quoted_token(self):
        self.assertEqual(
            worker.authenticated_repo_url("https://github.com/example/repo.git", "token/with space"),
            "https://x-access-token:token%2Fwith%20space@github.com/example/repo.git",
        )

    def test_parse_github_repo_extracts_owner_and_repo(self):
        self.assertEqual(
            worker.parse_github_repo("https://github.com/example/repo.git"),
            ("example", "repo"),
        )

    @patch("factory.worker.ssm_client")
    def test_load_github_token_reads_secure_parameter(self, ssm_client):
        client = Mock()
        client.get_parameter.return_value = {"Parameter": {"Value": "ghp_test"}}
        ssm_client.return_value = client

        with patch.dict(os.environ, {"GITHUB_TOKEN_PARAMETER_NAME": "/software-factory/dev/github-token"}):
            token = worker.load_github_token()

        self.assertEqual(token, "ghp_test")
        client.get_parameter.assert_called_once_with(
            Name="/software-factory/dev/github-token",
            WithDecryption=True,
        )

    @patch("factory.worker.subprocess.run")
    def test_create_factory_commit_creates_branch_and_commits_marker(self, run):
        run.return_value.stdout = "abc123\n"

        commit_sha = worker.create_factory_commit(
            Path("/tmp/workspace"),
            "factory/test-job-1",
            Path("/tmp/workspace/factory_run.txt"),
        )

        self.assertEqual(commit_sha, "abc123")
        run.assert_any_call(["git", "config", "user.name", "Software Factory"], cwd=Path("/tmp/workspace"), check=True)
        run.assert_any_call(
            ["git", "config", "user.email", "software-factory@example.local"],
            cwd=Path("/tmp/workspace"),
            check=True,
        )
        run.assert_any_call(["git", "checkout", "-b", "factory/test-job-1"], cwd=Path("/tmp/workspace"), check=True)
        run.assert_any_call(["git", "add", "factory_run.txt"], cwd=Path("/tmp/workspace"), check=True)
        run.assert_any_call(
            ["git", "commit", "-m", "Factory proof for factory/test-job-1"],
            cwd=Path("/tmp/workspace"),
            check=True,
        )
        run.assert_any_call(
            ["git", "rev-parse", "HEAD"],
            cwd=Path("/tmp/workspace"),
            check=True,
            capture_output=True,
            text=True,
        )

    @patch("factory.worker.subprocess.run")
    def test_push_factory_branch_sets_authenticated_remote_pushes_and_restores_remote(self, run):
        worker.push_factory_branch(
            Path("/tmp/workspace"),
            "https://github.com/example/repo.git",
            "factory/test-job-1",
            "ghp_test",
        )

        run.assert_any_call(
            [
                "git",
                "remote",
                "set-url",
                "origin",
                "https://x-access-token:ghp_test@github.com/example/repo.git",
            ],
            cwd=Path("/tmp/workspace"),
            check=True,
        )
        run.assert_any_call(
            ["git", "push", "origin", "factory/test-job-1"],
            cwd=Path("/tmp/workspace"),
            check=True,
        )
        run.assert_any_call(
            ["git", "remote", "set-url", "origin", "https://github.com/example/repo.git"],
            cwd=Path("/tmp/workspace"),
            check=True,
        )

    @patch("factory.worker.request.urlopen")
    def test_create_pull_request_posts_to_github_api(self, urlopen):
        response = Mock()
        response.read.return_value = json.dumps(
            {"html_url": "https://github.com/example/repo/pull/1", "number": 1}
        ).encode("utf-8")
        urlopen.return_value.__enter__.return_value = response

        pull_request = worker.create_pull_request(
            "https://github.com/example/repo.git",
            "factory/test-job-1",
            "fix the division bug",
            "ghp_test",
        )

        self.assertEqual(
            pull_request,
            {"url": "https://github.com/example/repo/pull/1", "number": 1},
        )
        pr_request = urlopen.call_args.args[0]
        self.assertEqual(pr_request.full_url, "https://api.github.com/repos/example/repo/pulls")
        self.assertEqual(pr_request.get_method(), "POST")
        self.assertEqual(pr_request.headers["Authorization"], "Bearer ghp_test")
        self.assertEqual(json.loads(pr_request.data.decode("utf-8"))["head"], "factory/test-job-1")
        self.assertEqual(json.loads(pr_request.data.decode("utf-8"))["base"], "main")

    @patch(
        "factory.worker.create_pull_request",
        return_value={"url": "https://github.com/example/repo/pull/1", "number": 1},
    )
    @patch("factory.worker.load_github_token", return_value="ghp_test")
    @patch("factory.worker.push_factory_branch")
    @patch("factory.worker.create_factory_commit", return_value="abc123")
    @patch("factory.worker.write_factory_marker")
    @patch("factory.worker.count_workspace_files", side_effect=[44, 45])
    @patch("factory.worker.clone_repository")
    def test_worker_clones_repo_writes_marker_and_completes_job(
        self,
        clone_repository,
        count_workspace_files,
        write_factory_marker,
        create_factory_commit,
        push_factory_branch,
        load_github_token,
        create_pull_request,
    ):
        write_factory_marker.return_value = Path("/tmp/test-workspace/factory_run.txt")
        start_status("clone repo test", job_id="test-job-1")

        with patch.dict(
            os.environ,
            {
                "JOB_ID": "test-job-1",
                "TASK_TEXT": "clone repo test",
                "TASK_CONTEXT": json.dumps({"calculator": {"operation": "divide", "error": "boom"}}),
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
        self.assertEqual(count_workspace_files.call_count, 2)
        count_workspace_files.assert_any_call(Path("/tmp/test-workspace"))
        marker_args = write_factory_marker.call_args.args
        self.assertEqual(marker_args[:3], (Path("/tmp/test-workspace"), "test-job-1", "clone repo test"))
        self.assertIn("boom", marker_args[3])
        create_factory_commit.assert_called_once_with(
            Path("/tmp/test-workspace"),
            "factory/test-job-1",
            Path("/tmp/test-workspace/factory_run.txt"),
        )
        push_factory_branch.assert_called_once_with(
            Path("/tmp/test-workspace"),
            "https://github.com/abhiverma31/software-factory-prototype.git",
            "factory/test-job-1",
            "ghp_test",
        )
        create_pull_request.assert_called_once_with(
            "https://github.com/abhiverma31/software-factory-prototype.git",
            "factory/test-job-1",
            "clone repo test",
            "ghp_test",
        )
        self.assertEqual(status["state"], "completed")
        self.assertEqual(status["task"], "clone repo test")
        self.assertEqual(
            status["detail"],
            "Repository cloned successfully. File count changed from 44 to 45 after writing factory_run.txt. "
            "Created a factory pull request.",
        )
        self.assertEqual(status["branch_name"], "factory/test-job-1")
        self.assertEqual(status["commit_sha"], "abc123")
        self.assertIs(status["pushed_branch"], True)
        self.assertEqual(status["pull_request_url"], "https://github.com/example/repo/pull/1")
        self.assertEqual(status["pull_request_number"], 1)
        self.assertIn("boom", status["prompt_preview"])

    def test_worker_requires_job_id_task_text_and_repo_url(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(worker.main(), 2)
