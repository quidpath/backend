from django.test import TestCase

from Tazama.Services.EnhancedFinancialDataService import EnhancedFinancialDataService


class DashboardMetricConsistencyTests(TestCase):
    def setUp(self):
        self.svc = EnhancedFinancialDataService()

    def test_mock_case_expected_ratios(self):
        # Mock figures from user example
        record = {
            'total_revenue': 10150000.0,
            'cost_of_revenue': 0.0,
            'gross_profit': 10150000.0,
            'total_operating_expenses': 1460000.0,
            'operating_income': 8690000.0,
            'net_income': 8690000.0,
            'research_development': 0.0,
        }

        metrics = self.svc._calculate_derived_metrics(record)

        # Expected values
        expected_profit_margin = 8690000.0 / 10150000.0  # ~0.85616
        expected_operating_margin = 8690000.0 / 10150000.0
        expected_cost_ratio = 0.0
        expected_expense_ratio = 1460000.0 / 10150000.0  # ~0.14398

        self.assertAlmostEqual(metrics['profit_margin'], expected_profit_margin, places=6)
        self.assertAlmostEqual(metrics['operating_margin'], expected_operating_margin, places=6)
        self.assertAlmostEqual(metrics['cost_revenue_ratio'], expected_cost_ratio, places=6)
        self.assertAlmostEqual(metrics['expense_ratio'], expected_expense_ratio, places=6)


