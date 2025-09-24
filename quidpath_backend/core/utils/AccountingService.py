# AccountingService.py (full corrected code)
from decimal import Decimal
from django.db import transaction
from datetime import date
from quidpath_backend.core.utils.registry import ServiceRegistry


class AccountingService:
    """
    Service class to handle automatic journal entry creation for invoices, bills, expenses, etc.
    """

    def __init__(self, registry=None):
        self.registry = registry or ServiceRegistry()

    def get_or_create_default_accounts(self, corporate_id, required=None):
        """
        Get or create default accounts for a corporate.
        If required is provided, only check/create those; otherwise, create all defaults if missing.
        """
        default_configs = {
            "accounts_receivable": {"code": "1200", "name": "Accounts Receivable", "type": "ASSET"},
            "sales_revenue": {"code": "4000", "name": "Sales Revenue", "type": "REVENUE"},
            "vat_payable": {"code": "2200", "name": "VAT Payable", "type": "LIABILITY"},
            "accounts_payable": {"code": "2100", "name": "Accounts Payable", "type": "LIABILITY"},
            "operating_expense": {"code": "6000", "name": "Operating Expenses", "type": "EXPENSE"},
            "vat_receivable": {"code": "1210", "name": "VAT Receivable", "type": "ASSET"},
            "cost_of_goods_sold": {"code": "5000", "name": "Cost of Goods Sold", "type": "EXPENSE"},
            "cash": {"code": "1100", "name": "Cash", "type": "ASSET"},
        }

        accounts = {}
        to_check = required if required is not None else list(default_configs.keys())

        for key in to_check:
            if key not in default_configs:
                continue
            config = default_configs[key]

            # Get or create account type
            type_data = self.registry.database(
                model_name="AccountType",
                operation="filter",
                data={"name": config["type"]}
            )
            if not type_data:
                new_type = self.registry.database(
                    model_name="AccountType",
                    operation="create",
                    data={"name": config["type"], "description": f"{config['type']} accounts"}
                )
                type_id = new_type["id"]
            else:
                type_id = type_data[0]["id"]

            # Get or create account
            account_data = self.registry.database(
                model_name="Account",
                operation="filter",
                data={"corporate_id": corporate_id, "code": config["code"]}
            ) or self.registry.database(
                model_name="Account",
                operation="filter",
                data={"corporate_id": corporate_id, "name": config["name"]}
            )

            if not account_data:
                new_account_data = {
                    "corporate_id": corporate_id,
                    "code": config["code"],
                    "name": config["name"],
                    "account_type_id": type_id,
                    "is_active": True,
                    "description": f"Default {config['name']} account"
                }
                new_account = self.registry.database(
                    model_name="Account",
                    operation="create",
                    data=new_account_data
                )
                accounts[key] = new_account["id"]
            else:
                accounts[key] = account_data[0]["id"]

        return accounts

    def create_invoice_journal_entry(self, invoice_id, user):
        """
        Create journal entry for a posted invoice
        Dr. Accounts Receivable
        Dr. VAT Input (if applicable)
        Cr. Sales Revenue
        """
        # Get invoice data
        invoices = self.registry.database(
            model_name="Invoices",
            operation="filter",
            data={"id": invoice_id}
        )

        if not invoices:
            raise ValueError("Invoice not found")

        invoice = invoices[0]

        # Get invoice lines
        lines = self.registry.database(
            model_name="InvoiceLine",
            operation="filter",
            data={"invoice_id": invoice_id}
        )

        # Get or create default accounts
        required_accounts = ["accounts_receivable", "sales_revenue", "vat_payable"]
        accounts = self.get_or_create_default_accounts(invoice["corporate_id"], required=required_accounts)

        with transaction.atomic():
            # Create journal entry
            je_data = {
                "corporate_id": invoice["corporate_id"],
                "date": invoice["date"],
                "reference": f"INV-{invoice['number']}",
                "description": f"Sales invoice {invoice['number']}",
                "source_type": "invoice",
                "source_id": invoice_id,
                "created_by_id": user.get("id") if isinstance(user, dict) else getattr(user, 'id'),
                "is_posted": True
            }

            journal_entry = self.registry.database(
                model_name="JournalEntry",
                operation="create",
                data=je_data
            )

            total_amount = Decimal(str(invoice.get("total", 0)))
            tax_total = Decimal(str(invoice.get("tax_total", 0)))
            revenue_amount = total_amount - tax_total

            # Dr. Accounts Receivable (total amount including tax)
            self.registry.database(
                model_name="JournalEntryLine",
                operation="create",
                data={
                    "journal_entry_id": journal_entry["id"],
                    "account_id": accounts["accounts_receivable"],
                    "debit": float(total_amount),
                    "credit": 0.00,
                    "description": f"Invoice {invoice['number']} - Customer receivable"
                }
            )

            # Cr. Sales Revenue (net amount)
            if revenue_amount > 0:
                self.registry.database(
                    model_name="JournalEntryLine",
                    operation="create",
                    data={
                        "journal_entry_id": journal_entry["id"],
                        "account_id": accounts["sales_revenue"],
                        "debit": 0.00,
                        "credit": float(revenue_amount),
                        "description": f"Invoice {invoice['number']} - Sales revenue"
                    }
                )

            # Cr. VAT Payable (tax amount)
            if tax_total > 0:
                self.registry.database(
                    model_name="JournalEntryLine",
                    operation="create",
                    data={
                        "journal_entry_id": journal_entry["id"],
                        "account_id": accounts["vat_payable"],
                        "debit": 0.00,
                        "credit": float(tax_total),
                        "description": f"Invoice {invoice['number']} - VAT collected"
                    }
                )

            return journal_entry

    def create_vendor_bill_journal_entry(self, vendor_bill_id, user):
        """
        Create journal entry for a posted vendor bill
        Dr. Expense/Inventory Account
        Dr. VAT Input (if applicable)
        Cr. Accounts Payable
        """
        # Get vendor bill data
        vendor_bills = self.registry.database(
            model_name="VendorBill",
            operation="filter",
            data={"id": vendor_bill_id}
        )

        if not vendor_bills:
            raise ValueError("Vendor bill not found")

        vendor_bill = vendor_bills[0]

        # Get vendor bill lines
        lines = self.registry.database(
            model_name="VendorBillLine",
            operation="filter",
            data={"vendor_bill_id": vendor_bill_id}
        )

        # Get or create default accounts
        required_accounts = ["accounts_payable", "operating_expense", "vat_receivable"]
        accounts = self.get_or_create_default_accounts(vendor_bill["corporate_id"], required=required_accounts)

        with transaction.atomic():
            # Create journal entry
            je_data = {
                "corporate_id": vendor_bill["corporate_id"],
                "date": vendor_bill["date"],
                "reference": f"BILL-{vendor_bill['number']}",
                "description": f"Vendor bill {vendor_bill['number']}",
                "source_type": "vendor_bill",
                "source_id": vendor_bill_id,
                "created_by_id": user.get("id") if isinstance(user, dict) else getattr(user, 'id'),
                "is_posted": True
            }

            journal_entry = self.registry.database(
                model_name="JournalEntry",
                operation="create",
                data=je_data
            )

            total_amount = Decimal(str(vendor_bill.get("total", 0)))
            tax_total = Decimal(str(vendor_bill.get("tax_total", 0)))
            expense_amount = total_amount - tax_total

            # Dr. Operating Expense (net amount)
            if expense_amount > 0:
                self.registry.database(
                    model_name="JournalEntryLine",
                    operation="create",
                    data={
                        "journal_entry_id": journal_entry["id"],
                        "account_id": accounts["operating_expense"],
                        "debit": float(expense_amount),
                        "credit": 0.00,
                        "description": f"Bill {vendor_bill['number']} - Operating expense"
                    }
                )

            # Dr. VAT Receivable (tax amount)
            if tax_total > 0:
                self.registry.database(
                    model_name="JournalEntryLine",
                    operation="create",
                    data={
                        "journal_entry_id": journal_entry["id"],
                        "account_id": accounts["vat_receivable"],
                        "debit": float(tax_total),
                        "credit": 0.00,
                        "description": f"Bill {vendor_bill['number']} - VAT input"
                    }
                )

            # Cr. Accounts Payable (total amount)
            self.registry.database(
                model_name="JournalEntryLine",
                operation="create",
                data={
                    "journal_entry_id": journal_entry["id"],
                    "account_id": accounts["accounts_payable"],
                    "debit": 0.00,
                    "credit": float(total_amount),
                    "description": f"Bill {vendor_bill['number']} - Vendor payable"
                }
            )

            return journal_entry

    def create_expense_journal_entry(self, expense_id, user):
        """
        Create journal entry for a direct expense
        Dr. Expense Account
        Dr. VAT Input (if applicable)
        Cr. Cash/Bank Account
        """
        # Get expense data
        expenses = self.registry.database(
            model_name="Expense",
            operation="filter",
            data={"id": expense_id}
        )

        if not expenses:
            raise ValueError("Expense not found")

        expense = expenses[0]

        total_amount = Decimal(str(expense["amount"])) + Decimal(str(expense.get("tax_amount", 0)))
        tax_amount = Decimal(str(expense.get("tax_amount", 0)))

        # Get or create default accounts if needed (only vat_receivable if tax > 0)
        required = ["vat_receivable"] if tax_amount > 0 else []
        accounts = self.get_or_create_default_accounts(expense["corporate_id"], required=required)

        with transaction.atomic():
            # Create journal entry
            je_data = {
                "corporate_id": expense["corporate_id"],
                "date": expense["date"],
                "reference": f"EXP-{expense['reference']}",
                "description": expense["description"],
                "source_type": "expense",
                "source_id": expense_id,
                "created_by_id": user.get("id") if isinstance(user, dict) else getattr(user, 'id'),
                "is_posted": True
            }

            journal_entry = self.registry.database(
                model_name="JournalEntry",
                operation="create",
                data=je_data
            )

            amount = Decimal(str(expense["amount"]))

            # Dr. Expense Account
            self.registry.database(
                model_name="JournalEntryLine",
                operation="create",
                data={
                    "journal_entry_id": journal_entry["id"],
                    "account_id": expense["expense_account_id"],
                    "debit": float(amount),
                    "credit": 0.00,
                    "description": expense["description"]
                }
            )

            # Dr. VAT Input (if applicable)
            if tax_amount > 0 and expense.get("tax_rate_id"):
                vat_receivable_id = accounts.get("vat_receivable")
                if vat_receivable_id:
                    self.registry.database(
                        model_name="JournalEntryLine",
                        operation="create",
                        data={
                            "journal_entry_id": journal_entry["id"],
                            "account_id": vat_receivable_id,
                            "debit": float(tax_amount),
                            "credit": 0.00,
                            "description": f"{expense['description']} - VAT input"
                        }
                    )

            # Cr. Payment Account
            self.registry.database(
                model_name="JournalEntryLine",
                operation="create",
                data={
                    "journal_entry_id": journal_entry["id"],
                    "account_id": expense["payment_account_id"],
                    "debit": 0.00,
                    "credit": float(total_amount),
                    "description": f"{expense['description']} - Payment"
                }
            )

            return journal_entry

    def create_payment_journal_entry(self, payment_id, user, payment_model="Payment"):
        """
        Create journal entry for a payment
        For customer payment: Dr. Cash/Bank, Cr. Accounts Receivable
        For vendor payment: Dr. Accounts Payable, Cr. Cash/Bank
        """
        # Get payment data from the specified model
        payments = self.registry.database(
            model_name=payment_model,
            operation="filter",
            data={"id": payment_id}
        )

        if not payments:
            raise ValueError(f"{payment_model} not found")

        payment = payments[0]

        # Determine payment_type based on model
        if payment_model == "RecordPayment":
            payment_type = "CUSTOMER_PAYMENT"
        elif payment_model == "VendorPayment":
            payment_type = "VENDOR_PAYMENT"
        else:
            raise ValueError("Invalid payment model")

        # Get or create default accounts based on payment type
        if payment_type == "CUSTOMER_PAYMENT":
            required = ["accounts_receivable"]
        elif payment_type == "VENDOR_PAYMENT":
            required = ["accounts_payable"]
        else:
            required = []
        accounts = self.get_or_create_default_accounts(payment["corporate_id"], required=required)

        with transaction.atomic():
            # Create journal entry
            je_data = {
                "corporate_id": payment["corporate_id"],
                "date": payment["payment_date"],  # Adjusted to use payment_date
                "reference": f"PAY-{payment.get('payment_number', payment['id'])}",
                "description": payment.get("notes", f"{payment_type} payment"),
                "source_type": "payment",
                "source_id": payment_id,
                "created_by_id": user.get("id") if isinstance(user, dict) else getattr(user, 'id'),
                "is_posted": True
            }

            journal_entry = self.registry.database(
                model_name="JournalEntry",
                operation="create",
                data=je_data
            )

            amount = Decimal(str(payment.get("amount_disbursed", payment.get("amount_received", 0))))

            if payment_type == "CUSTOMER_PAYMENT":
                # Dr. Bank Account
                self.registry.database(
                    model_name="JournalEntryLine",
                    operation="create",
                    data={
                        "journal_entry_id": journal_entry["id"],
                        "account_id": payment["account_id"],
                        "debit": float(amount),
                        "credit": 0.00,
                        "description": f"Customer payment {payment.get('payment_number', payment['id'])}"
                    }
                )

                # Cr. Accounts Receivable
                self.registry.database(
                    model_name="JournalEntryLine",
                    operation="create",
                    data={
                        "journal_entry_id": journal_entry["id"],
                        "account_id": accounts["accounts_receivable"],
                        "debit": 0.00,
                        "credit": float(amount),
                        "description": f"Customer payment {payment.get('payment_number', payment['id'])}"
                    }
                )

            elif payment_type == "VENDOR_PAYMENT":
                # Dr. Accounts Payable
                self.registry.database(
                    model_name="JournalEntryLine",
                    operation="create",
                    data={
                        "journal_entry_id": journal_entry["id"],
                        "account_id": accounts["accounts_payable"],
                        "debit": float(amount),
                        "credit": 0.00,
                        "description": f"Vendor payment {payment.get('payment_number', payment['id'])}"
                    }
                )

                # Cr. Bank Account
                self.registry.database(
                    model_name="JournalEntryLine",
                    operation="create",
                    data={
                        "journal_entry_id": journal_entry["id"],
                        "account_id": payment["account_id"],
                        "debit": 0.00,
                        "credit": float(amount),
                        "description": f"Vendor payment {payment.get('payment_number', payment['id'])}"
                    }
                )

            return journal_entry

    def setup_default_chart_of_accounts(self, corporate_id):
        """
        Set up a basic chart of accounts for a new corporate by creating all defaults.
        """
        return self.get_or_create_default_accounts(corporate_id)