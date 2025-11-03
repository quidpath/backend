"""
Test script for Universal Financial Parser
==========================================
Demonstrates various input formats and validates parsing accuracy
"""

import sys
import os
from pathlib import Path
import tempfile
import csv

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from UniversalFinancialParser import parse_financial_statement


def create_test_income_statement():
    """Create a test income statement CSV"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', newline='') as f:
        writer = csv.writer(f)
        
        # Write header
        writer.writerow(['Section', 'Item', 'Amount (KES)'])
        
        # Write data
        writer.writerow(['Revenue', 'Sales Revenue', '850,000'])
        writer.writerow(['Revenue', 'Service Revenue', '150,000'])
        writer.writerow(['Revenue', 'Total Revenue', '1,000,000'])
        writer.writerow(['Expenses', 'Salaries & Wages', '300,000'])
        writer.writerow(['Expenses', 'Rent', '50,000'])
        writer.writerow(['Expenses', 'Utilities', '20,000'])
        writer.writerow(['Expenses', 'Marketing', '40,000'])
        writer.writerow(['Expenses', 'Office Supplies', '15,000'])
        writer.writerow(['Expenses', 'Transport', '25,000'])
        writer.writerow(['Expenses', 'Miscellaneous', '10,000'])
        writer.writerow(['Expenses', 'Total Expenses', '460,000'])
        writer.writerow(['Net Income', 'Profit Before Tax', '540,000'])
        
        return f.name


def create_test_balance_sheet():
    """Create a test balance sheet CSV"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', newline='') as f:
        writer = csv.writer(f)
        
        # Write header
        writer.writerow(['Category', 'Item', 'Amount (KES)'])
        
        # Write data
        writer.writerow(['Assets', 'Cash', '1,200,000'])
        writer.writerow(['Assets', 'Accounts Receivable', '400,000'])
        writer.writerow(['Assets', 'Inventory', '300,000'])
        writer.writerow(['Assets', 'Total Assets', '1,900,000'])
        writer.writerow(['Liabilities', 'Accounts Payable', '250,000'])
        writer.writerow(['Liabilities', 'Short-term Debt', '200,000'])
        writer.writerow(['Liabilities', 'Total Liabilities', '450,000'])
        writer.writerow(['Equity', 'Share Capital', '100,000'])
        writer.writerow(['Equity', 'Retained Earnings', '1,350,000'])
        writer.writerow(['Equity', 'Total Equity', '1,450,000'])
        
        return f.name


def create_test_with_abbreviations():
    """Create a test with abbreviated amounts"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', newline='') as f:
        writer = csv.writer(f)
        
        # Write header
        writer.writerow(['Account', 'Q4 2025 (KES)'])
        
        # Write data with abbreviations
        writer.writerow(['Total Revenue', '1.5M'])
        writer.writerow(['Operating Expenses', '650K'])
        writer.writerow(['Net Profit', '850K'])
        
        return f.name


def run_test(test_name: str, file_path: str):
    """Run a single test case"""
    print("\n" + "=" * 80)
    print(f"TEST: {test_name}")
    print("=" * 80)
    
    try:
        result = parse_financial_statement(file_path)
        
        if result['success']:
            print("\n✅ PARSING SUCCESSFUL\n")
            print(result['summary'])
            
            # Validate metrics
            metrics = result['structured_data']['current_metrics']
            print("\n📊 VALIDATION:")
            print(f"  - Total Revenue: KES {metrics.get('total_revenue', 0):,.2f}")
            print(f"  - Net Income: KES {metrics.get('net_income', 0):,.2f}")
            
            if metrics.get('total_revenue', 0) > 0:
                print(f"  - Profit Margin: {metrics.get('profit_margin', 0):.1f}%")
            
            # Check projections
            if result['structured_data'].get('projections'):
                proj = result['structured_data']['projections']
                print(f"\n🔮 PROJECTIONS ({proj.get('period_label', 'N/A')}):")
                print(f"  - Projected Revenue: KES {proj.get('projected_revenue', 0):,.2f}")
                print(f"  - Revenue Growth: +{proj.get('revenue_growth', 0):.1f}%")
        else:
            print(f"\n❌ PARSING FAILED: {result.get('error')}")
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up temp file
        if os.path.exists(file_path):
            os.unlink(file_path)


def main():
    """Run all tests"""
    print("\n🚀 UNIVERSAL FINANCIAL PARSER - TEST SUITE")
    print("=" * 80)
    
    # Test 1: Standard Income Statement
    file1 = create_test_income_statement()
    run_test("Standard Income Statement (Tabular Format)", file1)
    
    # Test 2: Balance Sheet
    file2 = create_test_balance_sheet()
    run_test("Balance Sheet", file2)
    
    # Test 3: Abbreviated Amounts
    file3 = create_test_with_abbreviations()
    run_test("Statement with Abbreviated Amounts (1.5M, 650K)", file3)
    
    print("\n" + "=" * 80)
    print("✅ ALL TESTS COMPLETED")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()



