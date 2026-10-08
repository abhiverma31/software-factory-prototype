from django.test import TestCase
from django.urls import reverse

from . import services


class CalculatorServiceTests(TestCase):
    def test_basic_operations(self):
        self.assertEqual(services.add(2, 3), 5)
        self.assertEqual(services.subtract(7, 2), 5)
        self.assertEqual(services.multiply(4, 3), 12)
        self.assertEqual(services.divide(8, 2), 4)


class CalculatorViewTests(TestCase):
    def test_page_loads_with_clean_calculator_data(self):
        response = self.client.get(reverse("calculator"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Software Factory")

    def test_division_result_is_visible_to_user_after_repair(self):
        response = self.client.post(
            reverse("calculator"),
            {"left": "42", "right": "2", "operation": "divide"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Result")
        self.assertContains(response, "21")

