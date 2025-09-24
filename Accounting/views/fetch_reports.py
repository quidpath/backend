# reports.py
from decimal import Decimal
from django.views.decorators.csrf import csrf_exempt
from collections import defaultdict
import datetime
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.request_parser import get_clean_data
from quidpath_backend.core.utils.Logbase import TransactionLogBase

@csrf_exempt
def get_balance_sheet(request):
    """
    Retrieve the balance sheet for the user's corporate as of a specific date.

    Expected data (optional):
    - as_of_date: Date in YYYY-MM-DD format (default: today)

    Returns:
    - 200: Balance sheet data
    - 400: Bad request (invalid data)
    - 401: Unauthorized (user not authenticated)
    - 500: Internal server error
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    user_id = user.get("id") if isinstance(user, dict) else getattr(user, 'id', None)
    if not user_id:
        return ResponseProvider(message="User ID not found", code=400).bad_request()

    try:
        registry = ServiceRegistry()

        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user_id, "is_active": True}
        )
        if not corporate_users:
            return ResponseProvider(message="User has no corporate association", code=400).bad_request()

        corporate_id = corporate_users[0]["corporate_id"]
        if not corporate_id:
            return ResponseProvider(message="Corporate ID not found", code=400).bad_request()

        # Parse as_of_date
        as_of_date_raw = data.get("as_of_date")
        if isinstance(as_of_date_raw, str):
            as_of_date = datetime.date.fromisoformat(as_of_date_raw)
        elif isinstance(as_of_date_raw, datetime.datetime):
            as_of_date = as_of_date_raw.date()
        elif isinstance(as_of_date_raw, datetime.date):
            as_of_date = as_of_date_raw
        else:
            as_of_date = datetime.date.today()

        # Get all journal entries for the corporate
        journal_entries = registry.database(
            model_name="JournalEntry",
            operation="filter",
            data={"corporate_id": corporate_id, "is_posted": True}
        )

        # Filter relevant journal entries
        relevant_je = []
        for je in journal_entries:
            je_date = je.get("date")
            if isinstance(je_date, str):
                try:
                    je_date = datetime.date.fromisoformat(je_date)
                except ValueError:
                    continue  # skip invalid date strings
            elif isinstance(je_date, datetime.datetime):
                je_date = je_date.date()
            elif not isinstance(je_date, datetime.date):
                continue  # skip if not a valid date type

            if je_date <= as_of_date:
                relevant_je.append(je)

        je_ids = {je["id"] for je in relevant_je}

        # Get journal entry lines
        all_lines = registry.database(
            model_name="JournalEntryLine",
            operation="filter",
            data={}
        )
        lines = [line for line in all_lines if line["journal_entry_id"] in je_ids]

        balances = defaultdict(Decimal)
        for line in lines:
            balances[line["account_id"]] += Decimal(line["debit"]) - Decimal(line["credit"])

        # Fetch account types and subtypes
        account_types = registry.database(
            model_name="AccountType",
            operation="filter",
            data={}
        )
        type_map = {at["id"]: at["name"].upper() for at in account_types}

        sub_types = registry.database(
            model_name="AccountSubType",
            operation="filter",
            data={}
        )
        sub_type_map = {st["id"]: st["name"] for st in sub_types}

        accounts = registry.database(
            model_name="Account",
            operation="filter",
            data={"corporate_id": corporate_id, "is_active": True}
        )

        asset_sub = defaultdict(Decimal)
        liab_sub = defaultdict(Decimal)
        equity_sub = defaultdict(Decimal)

        for acc in accounts:
            bal = balances.get(acc["id"], Decimal("0.00"))
            type_upper = type_map.get(acc["account_type_id"], "")
            sub_name = sub_type_map.get(acc["account_sub_type_id"], "Unclassified")

            if type_upper == "ASSET":
                asset_sub[sub_name] += bal
            elif type_upper == "LIABILITY":
                liab_sub[sub_name] += -bal
            elif type_upper == "EQUITY":
                equity_sub[sub_name] += -bal

        total_asset = sum(asset_sub.values())
        total_liab = sum(liab_sub.values())
        total_equity = sum(equity_sub.values())

        bs_data = {
            "assets": {
                "subtypes": {k: str(v) for k, v in asset_sub.items()},
                "total": str(total_asset),
            },
            "liabilities": {
                "subtypes": {k: str(v) for k, v in liab_sub.items()},
                "total": str(total_liab),
            },
            "equity": {
                "subtypes": {k: str(v) for k, v in equity_sub.items()},
                "total": str(total_equity),
            },
            "as_of_date": str(as_of_date),
        }

        TransactionLogBase.log(
            transaction_type="BALANCE_SHEET_RETRIEVED",
            user=user,
            message="Balance sheet retrieved successfully",
            state_name="Success",
            extra={"as_of_date": str(as_of_date)},
            request=request,
        )

        return ResponseProvider(
            data=bs_data,
            message="Balance sheet retrieved successfully",
            code=200,
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="BALANCE_SHEET_RETRIEVAL_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while retrieving balance sheet", code=500
        ).exception()


@csrf_exempt
def get_income_statement(request):
    """
    Retrieve the income statement (profit and loss) for the user's corporate over a period.

    Expected data:
    - start_date: Start date in YYYY-MM-DD format (default: first day of current month)
    - end_date: End date in YYYY-MM-DD format (default: today)
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    user_id = user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
    if not user_id:
        return ResponseProvider(message="User ID not found", code=400).bad_request()

    try:
        registry = ServiceRegistry()

        # Corporate check
        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user_id, "is_active": True},
        )
        if not corporate_users:
            return ResponseProvider(message="User has no corporate association", code=400).bad_request()

        corporate_id = corporate_users[0].get("corporate_id")
        if not corporate_id:
            return ResponseProvider(message="Corporate ID not found", code=400).bad_request()

        # Parse dates
        today = datetime.date.today()
        start_date_str = data.get("start_date")
        end_date_str = data.get("end_date")

        start_date = (
            today.replace(day=1) if not start_date_str else datetime.date.fromisoformat(str(start_date_str))
        )
        end_date = today if not end_date_str else datetime.date.fromisoformat(str(end_date_str))

        if start_date > end_date:
            return ResponseProvider(message="Start date must be before end date", code=400).bad_request()

        # Journal entries
        journal_entries = registry.database(
            model_name="JournalEntry",
            operation="filter",
            data={"corporate_id": corporate_id, "is_posted": True},
        )

        # Ensure all journal entry dates are valid date objects
        relevant_je = []
        for je in journal_entries:
            je_date = _safe_parse_date(je.get("date"))
            if je_date and start_date <= je_date <= end_date:
                relevant_je.append(je)

        je_ids = {je["id"] for je in relevant_je}
        lines_period = [line for line in registry.database(model_name="JournalEntryLine", operation="filter", data={}) if line["journal_entry_id"] in je_ids]

        balances_period = defaultdict(Decimal)
        for line in lines_period:
            balances_period[line["account_id"]] += Decimal(str(line["debit"])) - Decimal(str(line["credit"]))

        # Metadata
        account_types = registry.database(model_name="AccountType", operation="filter", data={})
        type_map = {at["id"]: at["name"].upper() for at in account_types}

        sub_types = registry.database(model_name="AccountSubType", operation="filter", data={})
        sub_type_map = {st["id"]: st["name"] for st in sub_types}

        accounts = registry.database(
            model_name="Account",
            operation="filter",
            data={"corporate_id": corporate_id, "is_active": True},
        )

        # Group revenue & expenses
        revenue_sub = defaultdict(Decimal)
        expense_sub = defaultdict(Decimal)

        for acc in accounts:
            bal = balances_period.get(acc["id"], Decimal("0.00"))
            type_upper = type_map.get(acc["account_type_id"], "")
            sub_name = sub_type_map.get(acc["account_sub_type_id"], "Unclassified")

            if type_upper == "REVENUE":
                revenue_sub[sub_name] += -bal  # revenue is normally credit balance
            elif type_upper == "EXPENSE":
                expense_sub[sub_name] += bal

        total_revenue = sum(revenue_sub.values())
        total_expense = sum(expense_sub.values())
        net_income = total_revenue - total_expense

        is_data = {
            "revenues": {
                "subtypes": {k: str(v) for k, v in revenue_sub.items()},
                "total": str(total_revenue),
            },
            "expenses": {
                "subtypes": {k: str(v) for k, v in expense_sub.items()},
                "total": str(total_expense),
            },
            "net_income": str(net_income),
            "start_date": str(start_date),
            "end_date": str(end_date),
        }

        TransactionLogBase.log(
            transaction_type="INCOME_STATEMENT_RETRIEVED",
            user=user,
            message="Income statement retrieved successfully",
            state_name="Success",
            extra={"period": f"{start_date} to {end_date}"},
            request=request,
        )

        return ResponseProvider(
            data=is_data, message="Income statement retrieved successfully", code=200
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="INCOME_STATEMENT_RETRIEVAL_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while retrieving income statement", code=500
        ).exception()

@csrf_exempt
def get_profit_and_loss(request):
    # Profit and Loss is synonymous with Income Statement
    return get_income_statement(request)

def _safe_parse_date(value):
    """Convert DB date field into a datetime.date or None."""
    if isinstance(value, datetime.date) and not isinstance(value, datetime.datetime):
        return value
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return datetime.date.fromisoformat(value)
        except ValueError:
            return None
    return None


@csrf_exempt
def get_cash_flow_statement(request):
    """
    Retrieve the cash flow statement for the user's corporate over a period using indirect method.
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    user_id = user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
    if not user_id:
        return ResponseProvider(message="User ID not found", code=400).bad_request()

    try:
        registry = ServiceRegistry()

        # Corporate check
        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user_id, "is_active": True},
        )
        if not corporate_users:
            return ResponseProvider(message="User has no corporate association", code=400).bad_request()

        corporate_id = corporate_users[0].get("corporate_id")
        if not corporate_id:
            return ResponseProvider(message="Corporate ID not found", code=400).bad_request()

        # Parse dates
        today = datetime.date.today()
        start_date_str = data.get("start_date")
        end_date_str = data.get("end_date")

        start_date = (
            today.replace(day=1) if not start_date_str else datetime.date.fromisoformat(str(start_date_str))
        )
        end_date = today if not end_date_str else datetime.date.fromisoformat(str(end_date_str))

        if start_date > end_date:
            return ResponseProvider(message="Start date must be before end date", code=400).bad_request()

        start_minus_one = start_date - datetime.timedelta(days=1)

        # Journal entries
        journal_entries = registry.database(
            model_name="JournalEntry",
            operation="filter",
            data={"corporate_id": corporate_id, "is_posted": True},
        )

        # ----- Balances at start -----
        relevant_je_start = []
        for je in journal_entries:
            je_date = _safe_parse_date(je.get("date"))
            if je_date and je_date <= start_minus_one:
                relevant_je_start.append(je)

        je_ids_start = {je["id"] for je in relevant_je_start}
        lines_start = [line for line in registry.database(model_name="JournalEntryLine", operation="filter", data={}) if line["journal_entry_id"] in je_ids_start]

        balances_start = defaultdict(Decimal)
        for line in lines_start:
            balances_start[line["account_id"]] += Decimal(str(line["debit"])) - Decimal(str(line["credit"]))

        # ----- Balances at end -----
        relevant_je_end = []
        for je in journal_entries:
            je_date = _safe_parse_date(je.get("date"))
            if je_date and je_date <= end_date:
                relevant_je_end.append(je)

        je_ids_end = {je["id"] for je in relevant_je_end}
        lines_end = [line for line in registry.database(model_name="JournalEntryLine", operation="filter", data={}) if line["journal_entry_id"] in je_ids_end]

        balances_end = defaultdict(Decimal)
        for line in lines_end:
            balances_end[line["account_id"]] += Decimal(str(line["debit"])) - Decimal(str(line["credit"]))

        # Metadata
        account_types = registry.database(model_name="AccountType", operation="filter", data={})
        type_map = {at["id"]: at["name"].upper() for at in account_types}

        sub_types = registry.database(model_name="AccountSubType", operation="filter", data={})
        sub_type_map = {st["id"]: st["name"] for st in sub_types}

        accounts = registry.database(
            model_name="Account",
            operation="filter",
            data={"corporate_id": corporate_id, "is_active": True},
        )

        # Subtotals at start
        asset_sub_start, liab_sub_start, equity_sub_start = defaultdict(Decimal), defaultdict(Decimal), defaultdict(Decimal)
        for acc in accounts:
            bal = balances_start.get(acc["id"], Decimal("0.00"))
            type_upper = type_map.get(acc["account_type_id"], "")
            sub_name = sub_type_map.get(acc["account_sub_type_id"], "Unclassified")
            if type_upper == "ASSET":
                asset_sub_start[sub_name] += bal
            elif type_upper == "LIABILITY":
                liab_sub_start[sub_name] += -bal
            elif type_upper == "EQUITY":
                equity_sub_start[sub_name] += -bal

        # Subtotals at end
        asset_sub_end, liab_sub_end, equity_sub_end = defaultdict(Decimal), defaultdict(Decimal), defaultdict(Decimal)
        for acc in accounts:
            bal = balances_end.get(acc["id"], Decimal("0.00"))
            type_upper = type_map.get(acc["account_type_id"], "")
            sub_name = sub_type_map.get(acc["account_sub_type_id"], "Unclassified")
            if type_upper == "ASSET":
                asset_sub_end[sub_name] += bal
            elif type_upper == "LIABILITY":
                liab_sub_end[sub_name] += -bal
            elif type_upper == "EQUITY":
                equity_sub_end[sub_name] += -bal

        # ----- Net income for period -----
        relevant_je_period = []
        for je in journal_entries:
            je_date = _safe_parse_date(je.get("date"))
            if je_date and start_date <= je_date <= end_date:
                relevant_je_period.append(je)

        je_ids_period = {je["id"] for je in relevant_je_period}
        lines_period = [line for line in registry.database(model_name="JournalEntryLine", operation="filter", data={}) if line["journal_entry_id"] in je_ids_period]

        balances_period = defaultdict(Decimal)
        for line in lines_period:
            balances_period[line["account_id"]] += Decimal(str(line["debit"])) - Decimal(str(line["credit"]))

        revenue_period = Decimal("0.00")
        expense_period = Decimal("0.00")
        for acc in accounts:
            bal = balances_period.get(acc["id"], Decimal("0.00"))
            type_upper = type_map.get(acc["account_type_id"], "")
            if type_upper == "REVENUE":
                revenue_period += -bal
            elif type_upper == "EXPENSE":
                expense_period += bal

        net_income = revenue_period - expense_period

        # ----- Cash flow classification -----
        cash_sub_types = ["Cash on Hand"]
        current_asset_sub_types = ["Accounts Receivable"]
        fixed_asset_sub_types = ["Office Equipment"]
        current_liab_sub_types = ["Accounts Payable", "VAT Payable"]
        long_term_liab_sub_types = []
        equity_sub_types = ["Owner's Capital"]

        # Changes
        change_cash = sum(asset_sub_end.get(st, Decimal("0.00")) - asset_sub_start.get(st, Decimal("0.00")) for st in cash_sub_types)
        change_current_assets = sum(asset_sub_end.get(st, Decimal("0.00")) - asset_sub_start.get(st, Decimal("0.00")) for st in current_asset_sub_types)
        change_fixed_assets = sum(asset_sub_end.get(st, Decimal("0.00")) - asset_sub_start.get(st, Decimal("0.00")) for st in fixed_asset_sub_types)
        change_current_liab = sum(liab_sub_end.get(st, Decimal("0.00")) - liab_sub_start.get(st, Decimal("0.00")) for st in current_liab_sub_types)
        change_long_term_liab = sum(liab_sub_end.get(st, Decimal("0.00")) - liab_sub_start.get(st, Decimal("0.00")) for st in long_term_liab_sub_types)
        change_equity = sum(equity_sub_end.get(st, Decimal("0.00")) - equity_sub_start.get(st, Decimal("0.00")) for st in equity_sub_types)

        # Cash flows (Indirect method)
        operating = net_income - change_current_assets + change_current_liab
        investing = -change_fixed_assets
        financing = change_long_term_liab + change_equity
        net_change = operating + investing + financing

        cf_data = {
            "operating_cash_flow": str(operating),
            "investing_cash_flow": str(investing),
            "financing_cash_flow": str(financing),
            "net_cash_change": str(net_change),
            "actual_cash_change": str(change_cash),
            "start_date": str(start_date),
            "end_date": str(end_date),
        }

        TransactionLogBase.log(
            transaction_type="CASH_FLOW_STATEMENT_RETRIEVED",
            user=user,
            message="Cash flow statement retrieved successfully",
            state_name="Success",
            extra={"period": f"{start_date} to {end_date}"},
            request=request,
        )

        return ResponseProvider(data=cf_data, message="Cash flow statement retrieved successfully", code=200).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="CASH_FLOW_STATEMENT_RETRIEVAL_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(message="An error occurred while retrieving cash flow statement", code=500).exception()