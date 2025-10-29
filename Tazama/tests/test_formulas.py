from django.test import TestCase
import pandas as pd
from Tazama.core.TazamaCore import FinancialDataProcessor


class FormulaTests(TestCase):
    def setUp(self):
        self.processor = FinancialDataProcessor()

    def test_margin_and_ratio_formulas_and_clamping(self):
        df = pd.DataFrame([
            {
                'totalRevenue': 1000.0,
                'netIncome': 120.0,
                'grossProfit': 400.0,
                'operatingIncome': 200.0,
                'totalOperatingExpenses': 150.0,
                'costOfRevenue': 600.0,
                'researchDevelopment': 0.0,
            },
            {
                'totalRevenue': 0.0,
                'netIncome': -50.0,
                'grossProfit': -10.0,
                'operatingIncome': -20.0,
                'totalOperatingExpenses': 500.0,
                'costOfRevenue': 300.0,
                'researchDevelopment': 0.0,
            }
        ])

        out = self.processor._create_financial_features(df.copy())
        # Row 0
        self.assertAlmostEqual(out.loc[0, 'profit_margin'], 0.12)
        self.assertAlmostEqual(out.loc[0, 'gross_margin'], 0.4)
        self.assertAlmostEqual(out.loc[0, 'operating_margin'], 0.2)
        self.assertAlmostEqual(out.loc[0, 'cost_revenue_ratio'], 0.6)
        self.assertAlmostEqual(out.loc[0, 'expense_ratio'], 0.15)

        # Row 1 revenue is zero, all ratios should be 0 and within [0,1]
        for col in ['profit_margin', 'gross_margin', 'operating_margin', 'cost_revenue_ratio', 'expense_ratio']:
            val = float(out.loc[1, col])
            self.assertGreaterEqual(val, 0.0)
            self.assertLessEqual(val, 1.0)
            self.assertEqual(val, 0.0)


