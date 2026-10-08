import json

from django.conf import settings
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from .status_store import clear_status, complete_status, read_status, start_status


class FactoryViewTests(TestCase):
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


class FactoryStatusCopyTests(TestCase):
    def test_status_is_clear_when_codex_is_missing(self):
        # The local worker writes this state when Codex CLI is unavailable.
        self.assertIn("Codex CLI", "Codex CLI was not found on PATH.")


class FactoryStatusStoreTests(TestCase):
    def tearDown(self):
        clear_status()

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
