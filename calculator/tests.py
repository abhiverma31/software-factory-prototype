from django.test import TestCase
from django.urls import reverse

from . import services


class CalculatorServiceTests(TestCase):
    def test_basic_operations(self):
        self.assertEqual(services.add(2, 3), 5)
        self.assertEqual(services.subtract(7, 2), 5)
        self.assertEqual(services.multiply(4, 3), 12)
        self.assertEqual(services.divide(8, 2), 4)

    def test_division_preserves_fractional_result(self):
        self.assertEqual(services.divide(11, 4), 2.75)

    def test_division_by_zero_raises(self):
        with self.assertRaises(ZeroDivisionError):
            services.divide(11, 0)


class CalculatorViewTests(TestCase):
    def test_calculate_returns_fractional_division_result(self):
        response = self.client.post(
            reverse("calculator-calculate"),
            {"left": 11, "right": 4, "operation": "divide"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"result": 2.75})

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

