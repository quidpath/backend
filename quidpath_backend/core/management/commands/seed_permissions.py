"""
Seed all ModulePermissions and assign every permission to the SUPERADMIN role.
Other roles get a sensible default subset.

Run: python manage.py seed_permissions
"""
from django.core.management.base import BaseCommand
from Authentication.models.module_permission import ModulePermission
from Authentication.models.role import Role


# ── All modules in the system ─────────────────────────────────────────────────
# Format: (codename, module_slug, name, path, icon_slug, sort_order)
ALL_PERMISSIONS = [
    # Dashboard
    ("dashboard.view",          "dashboard",    "Dashboard",            "/dashboard",                       "Dashboard",        1),

    # Finance / Accounting
    ("finance.view",            "finance",      "Finance",              "/finance",                         "AccountBalance",   10),
    ("finance.invoices",        "finance",      "Invoices",             "/finance/invoices",                "Receipt",          11),
    ("finance.quotations",      "finance",      "Quotations",           "/finance/quotations",              "RequestQuote",     12),
    ("finance.expenses",        "finance",      "Expenses",             "/finance/expenses",                "MoneyOff",         13),
    ("finance.vendor_bills",    "finance",      "Vendor Bills",         "/finance/vendor-bills",            "Description",      14),
    ("finance.purchase_orders", "finance",      "Purchase Orders",      "/finance/purchase-orders",         "ShoppingCart",     15),
    ("finance.customers",       "finance",      "Customers",            "/finance/customers",               "People",           16),
    ("finance.vendors",         "finance",      "Vendors",              "/finance/vendors",                 "Store",            17),
    ("finance.accounts",        "finance",      "Chart of Accounts",    "/finance/accounts",                "AccountTree",      18),
    ("finance.journals",        "finance",      "Journal Entries",      "/finance/journals",                "Book",             19),
    ("finance.reports",         "finance",      "Reports",              "/finance/reports",                 "BarChart",         20),

    # Banking
    ("banking.view",            "banking",      "Banking",              "/banking",                         "AccountBalance",   30),
    ("banking.accounts",        "banking",      "Bank Accounts",        "/banking/accounts",                "CreditCard",       31),
    ("banking.transactions",    "banking",      "Transactions",         "/banking/transactions",            "SwapHoriz",        32),
    ("banking.transfers",       "banking",      "Internal Transfers",   "/banking/transfers",               "CompareArrows",    33),
    ("banking.reconciliation",  "banking",      "Reconciliation",       "/banking/reconciliation",          "Balance",          34),

    # Inventory
    ("inventory.view",          "inventory",    "Inventory",            "/inventory",                       "Inventory",        40),
    ("inventory.products",      "inventory",    "Products",             "/inventory/products",              "Category",         41),
    ("inventory.warehouses",    "inventory",    "Warehouses",           "/inventory/warehouses",            "Warehouse",        42),
    ("inventory.stock",         "inventory",    "Stock Movements",      "/inventory/stock",                 "MoveToInbox",      43),
    ("inventory.counting",      "inventory",    "Stock Counting",       "/inventory/counting",              "FactCheck",        44),

    # Point of Sale
    ("pos.view",                "pos",          "Point of Sale",        "/pos",                             "PointOfSale",      50),
    ("pos.orders",              "pos",          "Orders",               "/pos/orders",                      "ShoppingBag",      51),
    ("pos.sessions",            "pos",          "Sessions",             "/pos/sessions",                    "Timer",            52),
    ("pos.promotions",          "pos",          "Promotions",           "/pos/promotions",                  "LocalOffer",       53),
    ("pos.suppliers",           "pos",          "Suppliers",            "/pos/suppliers",                   "LocalShipping",    54),
    ("pos.purchases",           "pos",          "Purchase Orders",      "/pos/purchases",                   "ShoppingCart",     55),

    # CRM
    ("crm.view",                "crm",          "CRM",                  "/crm",                             "People",           60),
    ("crm.contacts",            "crm",          "Contacts",             "/crm/contacts",                    "Contacts",         61),
    ("crm.pipeline",            "crm",          "Pipeline",             "/crm/pipeline",                    "Timeline",         62),
    ("crm.deals",               "crm",          "Deals",                "/crm/deals",                       "Handshake",        63),
    ("crm.campaigns",           "crm",          "Campaigns",            "/crm/campaigns",                   "Campaign",         64),

    # HRM
    ("hrm.view",                "hrm",          "HR Management",        "/hrm",                             "Badge",            70),
    ("hrm.employees",           "hrm",          "Employees",            "/hrm/employees",                   "Person",           71),
    ("hrm.departments",         "hrm",          "Departments",          "/hrm/departments",                 "CorporateFare",    72),
    ("hrm.leaves",              "hrm",          "Leave Management",     "/hrm/leaves",                      "EventBusy",        73),
    ("hrm.payroll",             "hrm",          "Payroll",              "/hrm/payroll",                     "Payments",         74),
    ("hrm.recruitment",         "hrm",          "Recruitment",          "/hrm/recruitment",                 "Work",             75),
    ("hrm.attendance",          "hrm",          "Attendance",           "/hrm/attendance",                  "AccessTime",       76),
    ("hrm.performance",         "hrm",          "Performance",          "/hrm/performance",                 "TrendingUp",       77),

    # Projects
    ("projects.view",           "projects",     "Projects",             "/projects",                        "FolderOpen",       80),
    ("projects.tasks",          "projects",     "Tasks",                "/projects/tasks",                  "Task",             81),
    ("projects.timelog",        "projects",     "Time Log",             "/projects/timelog",                "Timer",            82),
    ("projects.issues",         "projects",     "Issues",               "/projects/issues",                 "BugReport",        83),

    # Org Admin (manage own organisation users)
    ("org_admin.view",          "org_admin",    "Org Admin",            "/org-admin",                       "ManageAccounts",   90),
    ("org_admin.users",         "org_admin",    "Users",                "/org-admin/users",                 "Group",            91),
    ("org_admin.branding",      "org_admin",    "Logo & Branding",      "/org-admin/branding",              "Palette",          92),

    # Account / Billing (own account only)
    ("account.view",            "account",      "Account",              "/account",                         "AccountCircle",    95),
    ("account.billing",         "account",      "Billing",              "/account/billing",                 "Payment",          96),

    # Analytics
    ("analytics.view",          "analytics",    "Analytics",            "/analytics",                       "Analytics",        100),

    # Settings (own org settings)
    ("settings.view",           "settings",     "Settings",             "/settings",                        "Settings",         110),
]

# ── Which permissions each non-SUPERADMIN role gets by default ────────────────
ROLE_PERMISSIONS = {
    "ADMIN": [
        "dashboard.view",
        "finance.view", "finance.invoices", "finance.quotations", "finance.expenses",
        "finance.vendor_bills", "finance.purchase_orders", "finance.customers",
        "finance.vendors", "finance.accounts", "finance.journals", "finance.reports",
        "banking.view", "banking.accounts", "banking.transactions", "banking.transfers", "banking.reconciliation",
        "inventory.view", "inventory.products", "inventory.warehouses", "inventory.stock", "inventory.counting",
        "pos.view", "pos.orders", "pos.sessions", "pos.promotions", "pos.suppliers", "pos.purchases",
        "crm.view", "crm.contacts", "crm.pipeline", "crm.deals", "crm.campaigns",
        "hrm.view", "hrm.employees", "hrm.departments", "hrm.leaves", "hrm.payroll",
        "hrm.recruitment", "hrm.attendance", "hrm.performance",
        "projects.view", "projects.tasks", "projects.timelog", "projects.issues",
        "org_admin.view", "org_admin.users",
        "account.view", "account.billing",
        "analytics.view",
        "settings.view",
    ],
    "ACCOUNTANT": [
        "dashboard.view",
        "finance.view", "finance.invoices", "finance.quotations", "finance.expenses",
        "finance.vendor_bills", "finance.purchase_orders", "finance.customers",
        "finance.vendors", "finance.accounts", "finance.journals", "finance.reports",
        "banking.view", "banking.accounts", "banking.transactions", "banking.reconciliation",
        "analytics.view",
        "account.view",
    ],
    "MANAGER": [
        "dashboard.view",
        "finance.view", "finance.invoices", "finance.quotations", "finance.expenses",
        "finance.reports",
        "inventory.view", "inventory.products", "inventory.stock",
        "crm.view", "crm.contacts", "crm.pipeline", "crm.deals",
        "hrm.view", "hrm.employees", "hrm.leaves",
        "projects.view", "projects.tasks", "projects.timelog",
        "analytics.view",
        "account.view",
    ],
    "USER": [
        "dashboard.view",
        "finance.view", "finance.invoices",
        "crm.view", "crm.contacts",
        "projects.view", "projects.tasks", "projects.timelog",
        "account.view",
    ],
    "VIEWER": [
        "dashboard.view",
        "finance.view", "finance.reports",
        "analytics.view",
        "account.view",
    ],
}


class Command(BaseCommand):
    help = "Seed all ModulePermissions and assign them to roles"

    def handle(self, *args, **options):
        self.stdout.write("Seeding module permissions...")

        # ── 1. Create / update all permissions ───────────────────────────────
        perm_map: dict[str, ModulePermission] = {}
        created = updated = 0

        for codename, module_slug, name, path, icon_slug, sort_order in ALL_PERMISSIONS:
            obj, was_created = ModulePermission.objects.update_or_create(
                codename=codename,
                defaults={
                    "module_slug": module_slug,
                    "name": name,
                    "path": path,
                    "icon_slug": icon_slug,
                    "sort_order": sort_order,
                },
            )
            perm_map[codename] = obj
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"  Permissions: {created} created, {updated} updated"
        ))

        # ── 2. Assign ALL permissions to SUPERADMIN ───────────────────────────
        superadmin, _ = Role.objects.get_or_create(name="SUPERADMIN")
        all_perms = list(perm_map.values())
        superadmin.module_permissions.set(all_perms)
        self.stdout.write(self.style.SUCCESS(
            f"  SUPERADMIN: assigned all {len(all_perms)} permissions"
        ))

        # ── 3. Assign subset permissions to other roles ───────────────────────
        for role_name, codenames in ROLE_PERMISSIONS.items():
            role, _ = Role.objects.get_or_create(name=role_name)
            perms = [perm_map[c] for c in codenames if c in perm_map]
            role.module_permissions.set(perms)
            self.stdout.write(self.style.SUCCESS(
                f"  {role_name}: assigned {len(perms)} permissions"
            ))

        self.stdout.write(self.style.SUCCESS("\nDone — permissions seeded."))
