import json
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse


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
