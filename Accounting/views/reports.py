import json
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.views.decorators.csrf import csrf_exempt

from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.Logbase import TransactionLogBase
from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.request_parser import get_clean_data


def generate_pl_data(registry, corporate_id, start_date, end_date):
    """
    Generate Profit and Loss data using registry.
    """
    # Revenue
    revenue_types = registry.database("AccountType", "filter", data={"name": "REVENUE"})
    revenues = {}
    total_revenue = Decimal("0")
    if revenue_types:
        revenue_type_id = revenue_types[0]["id"]
        line_data = {
            "journal_entry__corporate_id": corporate_id,
            "journal_entry__is_posted": True,
            "journal_entry__date__gte": start_date,
            "journal_entry__date__lte": end_date,
            "account__account_type_id": revenue_type_id,
        }
        lines = registry.database("JournalEntryLine", "filter", data=line_data)
        account_ids = list(set(l["account_id"] for l in lines))
        subtype_dict = {}
        if account_ids:
            accounts = registry.database(
                "Account",
                "filter",
                data={"id__in": account_ids, "corporate_id": corporate_id},
            )
            subtype_dict = {
                acc["id"]: acc.get("account_sub_type__name", "Other Revenue")
                for acc in accounts
            }
        revenue_dict = defaultdict(Decimal)
        for line in lines:
            sub_name = subtype_dict.get(line["account_id"], "Other Revenue")
            balance = Decimal(str(line.get("credit", 0))) - Decimal(
                str(line.get("debit", 0))
            )
            revenue_dict[sub_name] += balance
        revenues = dict(revenue_dict)
        total_revenue = sum(revenue_dict.values())

    # Expenses
    expense_types = registry.database("AccountType", "filter", data={"name": "EXPENSE"})
    expenses = {}
    total_expenses = Decimal("0")
    if expense_types:
        expense_type_id = expense_types[0]["id"]
        line_data = {
            "journal_entry__corporate_id": corporate_id,
            "journal_entry__is_posted": True,
            "journal_entry__date__gte": start_date,
            "journal_entry__date__lte": end_date,
            "account__account_type_id": expense_type_id,
        }
        lines = registry.database("JournalEntryLine", "filter", data=line_data)
        account_ids = list(set(l["account_id"] for l in lines))
        subtype_dict = {}
        if account_ids:
            accounts = registry.database(
                "Account",
                "filter",
                data={"id__in": account_ids, "corporate_id": corporate_id},
            )
            subtype_dict = {
                acc["id"]: acc.get("account_sub_type__name", "Other Expense")
                for acc in accounts
            }
        expense_dict = defaultdict(Decimal)
        for line in lines:
            sub_name = subtype_dict.get(line["account_id"], "Other Expense")
            balance = Decimal(str(line.get("debit", 0))) - Decimal(
                str(line.get("credit", 0))
            )
            expense_dict[sub_name] += balance
        expenses = dict(expense_dict)
        total_expenses = sum(expense_dict.values())

    net_profit = total_revenue - total_expenses

    return {
        "revenues": {k: float(v) for k, v in revenues.items()},
        "total_revenues": float(total_revenue),
        "expenses": {k: float(v) for k, v in expenses.items()},
        "total_expenses": float(total_expenses),
        "net_profit": float(net_profit),
    }


def get_balance_sheet_data(registry, corporate_id, end_date, start_date=None):
    """
    Generate Balance Sheet data using registry.
    """
    net_profit = Decimal("0")
    if start_date:
        pl_data = generate_pl_data(registry, corporate_id, start_date, end_date)
        net_profit = Decimal(str(pl_data["net_profit"]))

    # Assets
    asset_types = registry.database("AccountType", "filter", data={"name": "ASSET"})
    assets_subtypes = {}
    total_assets = Decimal("0")
    cash_balance = Decimal("0")
    if asset_types:
        type_id = asset_types[0]["id"]
        line_data = {
            "journal_entry__corporate_id": corporate_id,
            "journal_entry__is_posted": True,
            "journal_entry__date__lte": end_date,
            "account__account_type_id": type_id,
        }
        lines = registry.database("JournalEntryLine", "filter", data=line_data)
        account_ids = list(set(l["account_id"] for l in lines))
        subtype_dict = {}
        if account_ids:
            accounts = registry.database(
                "Account",
                "filter",
                data={"id__in": account_ids, "corporate_id": corporate_id},
            )
            subtype_dict = {
                acc["id"]: acc.get("account_sub_type__name")
                for acc in accounts
                if acc.get("account_sub_type__name")
            }
        assets_dict = defaultdict(Decimal)
        for line in lines:
            acc_id = line["account_id"]
            sub_name = subtype_dict.get(acc_id)
            if sub_name:
                balance = Decimal(str(line.get("debit", 0))) - Decimal(
                    str(line.get("credit", 0))
                )
                assets_dict[sub_name] += balance
                if "cash" in sub_name.lower():
                    cash_balance += balance
        assets_subtypes = dict(assets_dict)
        total_assets = sum(assets_dict.values())

    # Liabilities
    liab_types = registry.database("AccountType", "filter", data={"name": "LIABILITY"})
    liab_subtypes = {}
    total_liabilities = Decimal("0")
    if liab_types:
        type_id = liab_types[0]["id"]
        line_data = {
            "journal_entry__corporate_id": corporate_id,
            "journal_entry__is_posted": True,
            "journal_entry__date__lte": end_date,
            "account__account_type_id": type_id,
        }
        lines = registry.database("JournalEntryLine", "filter", data=line_data)
        account_ids = list(set(l["account_id"] for l in lines))
        subtype_dict = {}
        if account_ids:
            accounts = registry.database(
                "Account",
                "filter",
                data={"id__in": account_ids, "corporate_id": corporate_id},
            )
            subtype_dict = {
                acc["id"]: acc.get("account_sub_type__name")
                for acc in accounts
                if acc.get("account_sub_type__name")
            }
        liab_dict = defaultdict(Decimal)
        for line in lines:
            sub_name = subtype_dict.get(line["account_id"])
            if sub_name:
                balance = Decimal(str(line.get("credit", 0))) - Decimal(
                    str(line.get("debit", 0))
                )
                liab_dict[sub_name] += balance
        liab_subtypes = dict(liab_dict)
        total_liabilities = sum(liab_dict.values())

    # Equity
    equity_types = registry.database("AccountType", "filter", data={"name": "EQUITY"})
    equity_subtypes = {}
    total_equity = Decimal("0")
    if equity_types:
        type_id = equity_types[0]["id"]
        line_data = {
            "journal_entry__corporate_id": corporate_id,
            "journal_entry__is_posted": True,
            "journal_entry__date__lte": end_date,
            "account__account_type_id": type_id,
        }
        lines = registry.database("JournalEntryLine", "filter", data=line_data)
        account_ids = list(set(l["account_id"] for l in lines))
        subtype_dict = {}
        if account_ids:
            accounts = registry.database(
                "Account",
                "filter",
                data={"id__in": account_ids, "corporate_id": corporate_id},
            )
            subtype_dict = {
                acc["id"]: acc.get("account_sub_type__name")
                for acc in accounts
                if acc.get("account_sub_type__name")
            }
        equity_dict = defaultdict(Decimal)
        for line in lines:
            sub_name = subtype_dict.get(line["account_id"])
            if sub_name:
                balance = Decimal(str(line.get("credit", 0))) - Decimal(
                    str(line.get("debit", 0))
                )
                equity_dict[sub_name] += balance
        if start_date:
            retained_key = next(
                (
                    k
                    for k in equity_dict
                    if "retained" in k.lower() and "earnings" in k.lower()
                ),
                None,
            )
            if retained_key:
                equity_dict[retained_key] += net_profit
            else:
                equity_dict["Net Profit for Period"] = net_profit
        equity_subtypes = dict(equity_dict)
        total_equity = sum(equity_dict.values())
    else:
        equity_subtypes = {"Net Profit for Period": float(net_profit)}
        total_equity = net_profit

    data = {
        "assets": {"subtypes": assets_subtypes, "total": float(total_assets)},
        "liabilities": {"subtypes": liab_subtypes, "total": float(total_liabilities)},
        "equity": {"subtypes": equity_subtypes, "total": float(total_equity)},
        "cash": float(cash_balance),
        "net_profit_for_period": float(net_profit),
    }
    return data


def generate_cash_flow_data(registry, corporate_id, start_date, end_date):
    """
    Generate Cash Flow data using registry.
    """
    pl_data = generate_pl_data(registry, corporate_id, start_date, end_date)
    net_income = Decimal(str(pl_data["net_profit"]))

    bs_end = get_balance_sheet_data(registry, corporate_id, end_date, start_date)

    start_bs_date = start_date - timedelta(days=1)
    bs_start = get_balance_sheet_data(registry, corporate_id, start_bs_date, None)

    cash_start = Decimal(str(bs_start["cash"]))
    cash_end = Decimal(str(bs_end["cash"]))

    total_assets_start = Decimal(str(bs_start["assets"]["total"]))
    total_assets_end = Decimal(str(bs_end["assets"]["total"]))
    delta_assets_ex_cash = (total_assets_end - cash_end) - (
        total_assets_start - cash_start
    )

    total_liab_start = Decimal(str(bs_start["liabilities"]["total"]))
    total_liab_end = Decimal(str(bs_end["liabilities"]["total"]))
    delta_liabilities = total_liab_end - total_liab_start

    operating_cash_flow = net_income - delta_assets_ex_cash + delta_liabilities

    delta_total_assets = total_assets_end - total_assets_start
    delta_cash = cash_end - cash_start
    investing_cash_flow = -(delta_total_assets - delta_cash)

    total_equity_start = Decimal(str(bs_start["equity"]["total"]))
    total_equity_end = Decimal(str(bs_end["equity"]["total"]))
    delta_equity = total_equity_end - total_equity_start
    financing_cash_flow = delta_liabilities + (delta_equity - net_income)

    net_change_in_cash = delta_cash

    return {
        "net_income": float(net_income),
        "operating_cash_flow": float(operating_cash_flow),
        "investing_cash_flow": float(investing_cash_flow),
        "financing_cash_flow": float(financing_cash_flow),
        "net_change_in_cash": float(net_change_in_cash),
        "beginning_cash": float(cash_start),
        "ending_cash": float(cash_end),
    }


@csrf_exempt
def generate_profit_loss_report(request):
    """
    Generate Profit and Loss report for the user's corporate.
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(
            message="User not authenticated", code=401
        ).unauthorized()

    user_id = user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
    if not user_id:
        return ResponseProvider(message="User ID not found", code=400).bad_request()

    try:
        registry = ServiceRegistry()

        corporate_users = registry.database(
            "CorporateUser",
            "filter",
            data={"customuser_ptr_id": user_id, "is_active": True},
        )
        if not corporate_users:
            return ResponseProvider(
                message="User has no corporate association", code=400
            ).bad_request()

        corporate_id = corporate_users[0]["corporate_id"]
        if not corporate_id:
            return ResponseProvider(
                message="Corporate ID not found", code=400
            ).bad_request()

        start_date_str = data.get("start_date")
        end_date_str = data.get("end_date")
        if not start_date_str or not end_date_str:
            return ResponseProvider(
                message="Start date and end date are required", code=400
            ).bad_request()

        start_date = date.fromisoformat(start_date_str)
        end_date = date.fromisoformat(end_date_str)

        report_data = generate_pl_data(registry, corporate_id, start_date, end_date)

        with transaction.atomic():
            financial_data = {
                "corporate_id": corporate_id,
                "report_type": "PROFIT_LOSS",
                "start_date": start_date,
                "end_date": end_date,
                "data": report_data,
            }
            report = registry.database("FinancialReport", "create", data=financial_data)

        TransactionLogBase.log(
            transaction_type="PROFIT_LOSS_REPORT_GENERATED",
            user=user,
            message=f"Profit and Loss report generated for corporate {corporate_id}",
            state_name="Completed",
            extra={"report_id": report["id"], "period": f"{start_date} to {end_date}"},
            request=request,
        )

        return ResponseProvider(
            message="Profit and Loss report generated successfully",
            data={"report_id": str(report["id"]), "data": report_data},
            code=201,
        ).success()

    except ValueError as e:
        return ResponseProvider(message=str(e), code=400).bad_request()
    except Exception as e:
        TransactionLogBase.log(
            transaction_type="PROFIT_LOSS_REPORT_GENERATION_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while generating report", code=500
        ).exception()


@csrf_exempt
def generate_income_statement_report(request):
    """
    Generate Income Statement report for the user's corporate (same as P&L).
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(
            message="User not authenticated", code=401
        ).unauthorized()

    user_id = user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
    if not user_id:
        return ResponseProvider(message="User ID not found", code=400).bad_request()

    try:
        registry = ServiceRegistry()

        corporate_users = registry.database(
            "CorporateUser",
            "filter",
            data={"customuser_ptr_id": user_id, "is_active": True},
        )
        if not corporate_users:
            return ResponseProvider(
                message="User has no corporate association", code=400
            ).bad_request()

        corporate_id = corporate_users[0]["corporate_id"]
        if not corporate_id:
            return ResponseProvider(
                message="Corporate ID not found", code=400
            ).bad_request()

        start_date_str = data.get("start_date")
        end_date_str = data.get("end_date")
        if not start_date_str or not end_date_str:
            return ResponseProvider(
                message="Start date and end date are required", code=400
            ).bad_request()

        start_date = date.fromisoformat(start_date_str)
        end_date = date.fromisoformat(end_date_str)

        report_data = generate_pl_data(registry, corporate_id, start_date, end_date)

        with transaction.atomic():
            financial_data = {
                "corporate_id": corporate_id,
                "report_type": "INCOME_STATEMENT",
                "start_date": start_date,
                "end_date": end_date,
                "data": report_data,
            }
            report = registry.database("FinancialReport", "create", data=financial_data)

        TransactionLogBase.log(
            transaction_type="INCOME_STATEMENT_REPORT_GENERATED",
            user=user,
            message=f"Income Statement report generated for corporate {corporate_id}",
            state_name="Completed",
            extra={"report_id": report["id"], "period": f"{start_date} to {end_date}"},
            request=request,
        )

        return ResponseProvider(
            message="Income Statement report generated successfully",
            data={"report_id": str(report["id"]), "data": report_data},
            code=201,
        ).success()

    except ValueError as e:
        return ResponseProvider(message=str(e), code=400).bad_request()
    except Exception as e:
        TransactionLogBase.log(
            transaction_type="INCOME_STATEMENT_REPORT_GENERATION_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while generating report", code=500
        ).exception()


@csrf_exempt
def generate_balance_sheet_report(request):
    """
    Generate Balance Sheet report for the user's corporate.
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(
            message="User not authenticated", code=401
        ).unauthorized()

    user_id = user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
    if not user_id:
        return ResponseProvider(message="User ID not found", code=400).bad_request()

    try:
        registry = ServiceRegistry()

        corporate_users = registry.database(
            "CorporateUser",
            "filter",
            data={"customuser_ptr_id": user_id, "is_active": True},
        )
        if not corporate_users:
            return ResponseProvider(
                message="User has no corporate association", code=400
            ).bad_request()

        corporate_id = corporate_users[0]["corporate_id"]
        if not corporate_id:
            return ResponseProvider(
                message="Corporate ID not found", code=400
            ).bad_request()

        end_date_str = data.get("end_date")
        start_date_str = data.get("start_date")
        if not end_date_str:
            return ResponseProvider(
                message="End date is required", code=400
            ).bad_request()

        start_date = date.fromisoformat(start_date_str) if start_date_str else None
        end_date = date.fromisoformat(end_date_str)

        report_data = get_balance_sheet_data(
            registry, corporate_id, end_date, start_date
        )

        with transaction.atomic():
            financial_data = {
                "corporate_id": corporate_id,
                "report_type": "BALANCE_SHEET",
                "start_date": start_date,
                "end_date": end_date,
                "data": report_data,
            }
            report = registry.database("FinancialReport", "create", data=financial_data)

        TransactionLogBase.log(
            transaction_type="BALANCE_SHEET_REPORT_GENERATED",
            user=user,
            message=f"Balance Sheet report generated for corporate {corporate_id}",
            state_name="Completed",
            extra={"report_id": report["id"], "as_of": end_date},
            request=request,
        )

        return ResponseProvider(
            message="Balance Sheet report generated successfully",
            data={"report_id": str(report["id"]), "data": report_data},
            code=201,
        ).success()

    except ValueError as e:
        return ResponseProvider(message=str(e), code=400).bad_request()
    except Exception as e:
        TransactionLogBase.log(
            transaction_type="BALANCE_SHEET_REPORT_GENERATION_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while generating report", code=500
        ).exception()


@csrf_exempt
def generate_cash_flow_report(request):
    """
    Generate Cash Flow report for the user's corporate.
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(
            message="User not authenticated", code=401
        ).unauthorized()

    user_id = user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
    if not user_id:
        return ResponseProvider(message="User ID not found", code=400).bad_request()

    try:
        registry = ServiceRegistry()

        corporate_users = registry.database(
            "CorporateUser",
            "filter",
            data={"customuser_ptr_id": user_id, "is_active": True},
        )
        if not corporate_users:
            return ResponseProvider(
                message="User has no corporate association", code=400
            ).bad_request()

        corporate_id = corporate_users[0]["corporate_id"]
        if not corporate_id:
            return ResponseProvider(
                message="Corporate ID not found", code=400
            ).bad_request()

        start_date_str = data.get("start_date")
        end_date_str = data.get("end_date")
        if not start_date_str or not end_date_str:
            return ResponseProvider(
                message="Start date and end date are required", code=400
            ).bad_request()

        start_date = date.fromisoformat(start_date_str)
        end_date = date.fromisoformat(end_date_str)

        report_data = generate_cash_flow_data(
            registry, corporate_id, start_date, end_date
        )

        with transaction.atomic():
            financial_data = {
                "corporate_id": corporate_id,
                "report_type": "CASH_FLOW",
                "start_date": start_date,
                "end_date": end_date,
                "data": report_data,
            }
            report = registry.database("FinancialReport", "create", data=financial_data)

        TransactionLogBase.log(
            transaction_type="CASH_FLOW_REPORT_GENERATED",
            user=user,
            message=f"Cash Flow report generated for corporate {corporate_id}",
            state_name="Completed",
            extra={"report_id": report["id"], "period": f"{start_date} to {end_date}"},
            request=request,
        )

        return ResponseProvider(
            message="Cash Flow report generated successfully",
            data={"report_id": str(report["id"]), "data": report_data},
            code=201,
        ).success()

    except ValueError as e:
        return ResponseProvider(message=str(e), code=400).bad_request()
    except Exception as e:
        TransactionLogBase.log(
            transaction_type="CASH_FLOW_REPORT_GENERATION_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while generating report", code=500
        ).exception()


@csrf_exempt
def retrieve_financial_report(request):
    """
    Retrieve a financial report by ID for the user's corporate.
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(
            message="User not authenticated", code=401
        ).unauthorized()

    user_id = user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
    if not user_id:
        return ResponseProvider(message="User ID not found", code=400).bad_request()

    try:
        registry = ServiceRegistry()

        corporate_users = registry.database(
            "CorporateUser",
            "filter",
            data={"customuser_ptr_id": user_id, "is_active": True},
        )
        if not corporate_users:
            return ResponseProvider(
                message="User has no corporate association", code=400
            ).bad_request()

        corporate_id = corporate_users[0]["corporate_id"]

        report_id = data.get("report_id") or request.GET.get("report_id")
        if not report_id:
            return ResponseProvider(
                message="Report ID is required", code=400
            ).bad_request()

        reports = registry.database(
            "FinancialReport",
            "filter",
            data={"id": report_id, "corporate_id": corporate_id},
        )
        if not reports:
            return ResponseProvider(
                message="Report not found for this corporate", code=404
            ).bad_request()

        report = reports[0]
        report_data = report["data"]

        TransactionLogBase.log(
            transaction_type="FINANCIAL_REPORT_RETRIEVED",
            user=user,
            message=f"Financial report {report_id} retrieved for corporate {corporate_id}",
            state_name="Success",
            extra={"report_type": report["report_type"]},
            request=request,
        )

        return ResponseProvider(
            message="Report retrieved successfully",
            data={"report_id": str(report["id"]), "data": report_data},
            code=200,
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="FINANCIAL_REPORT_RETRIEVE_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while retrieving report", code=500
        ).exception()


@csrf_exempt
def download_financial_report(request):
    """
    Download a financial report as CSV by ID.
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(
            message="User not authenticated", code=401
        ).unauthorized()

    user_id = user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
    if not user_id:
        return ResponseProvider(message="User ID not found", code=400).bad_request()

    try:
        registry = ServiceRegistry()

        corporate_users = registry.database(
            "CorporateUser",
            "filter",
            data={"customuser_ptr_id": user_id, "is_active": True},
        )
        if not corporate_users:
            return ResponseProvider(
                message="User has no corporate association", code=400
            ).bad_request()

        corporate_id = corporate_users[0]["corporate_id"]

        report_id = data.get("report_id") or request.GET.get("report_id")
        if not report_id:
            return ResponseProvider(
                message="Report ID is required", code=400
            ).bad_request()

        reports = registry.database(
            "FinancialReport",
            "filter",
            data={"id": report_id, "corporate_id": corporate_id},
        )
        if not reports:
            return ResponseProvider(
                message="Report not found for this corporate", code=404
            ).bad_request()

        report = reports[0]
        report_data = report["data"]
        report_type = report["report_type"]
        end_date = report["end_date"]

        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)
        filename = f"{report_type}_{end_date}.csv"

        if report_type in ["PROFIT_LOSS", "INCOME_STATEMENT"]:
            writer.writerow(["Section", "Description", "Amount"])
            writer.writerow(["Revenues", "", ""])
            for desc, amount in report_data.get("revenues", {}).items():
                writer.writerow(["", desc, amount])
            writer.writerow(
                ["", "Total Revenues", report_data.get("total_revenues", 0)]
            )

            writer.writerow(["Expenses", "", ""])
            for desc, amount in report_data.get("expenses", {}).items():
                writer.writerow(["", desc, amount])
            writer.writerow(
                ["", "Total Expenses", report_data.get("total_expenses", 0)]
            )

            writer.writerow(["Net Profit", "", report_data.get("net_profit", 0)])

        elif report_type == "BALANCE_SHEET":
            writer.writerow(["Assets", "", ""])
            for desc, amount in (
                report_data.get("assets", {}).get("subtypes", {}).items()
            ):
                writer.writerow(["", desc, amount])
            writer.writerow(
                ["Total Assets", "", report_data.get("assets", {}).get("total", 0)]
            )

            writer.writerow(["Liabilities", "", ""])
            for desc, amount in (
                report_data.get("liabilities", {}).get("subtypes", {}).items()
            ):
                writer.writerow(["", desc, amount])
            writer.writerow(
                [
                    "Total Liabilities",
                    "",
                    report_data.get("liabilities", {}).get("total", 0),
                ]
            )

            writer.writerow(["Equity", "", ""])
            for desc, amount in (
                report_data.get("equity", {}).get("subtypes", {}).items()
            ):
                writer.writerow(["", desc, amount])
            writer.writerow(
                ["Total Equity", "", report_data.get("equity", {}).get("total", 0)]
            )

        elif report_type == "CASH_FLOW":
            writer.writerow(["Cash Flow Statement", "", ""])
            writer.writerow(
                ["Operating Activities", report_data.get("operating_cash_flow", 0)]
            )
            writer.writerow(["Net Income", report_data.get("net_income", 0)])

            writer.writerow(
                ["Investing Activities", report_data.get("investing_cash_flow", 0)]
            )

            writer.writerow(
                ["Financing Activities", report_data.get("financing_cash_flow", 0)]
            )

            writer.writerow(
                ["Net Change in Cash", report_data.get("net_change_in_cash", 0)]
            )
            writer.writerow(["Beginning Cash", report_data.get("beginning_cash", 0)])
            writer.writerow(["Ending Cash", report_data.get("ending_cash", 0)])

        from django.http import HttpResponse

        response = HttpResponse(output.getvalue(), content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="FINANCIAL_REPORT_DOWNLOAD_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while downloading report", code=500
        ).exception()
