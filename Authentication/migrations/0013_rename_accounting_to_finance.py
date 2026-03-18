from django.db import migrations


def rename_accounting_to_finance(apps, schema_editor):
    ModulePermission = apps.get_model("Authentication", "ModulePermission")

    # Update parent "accounting" module
    ModulePermission.objects.filter(codename="accounting").update(
        name="Finance",
        path="/finance",
        module_slug="finance",
    )

    # Update children — point them to /finance with tab query params
    children = [
        ("accounting.invoices",  "Sales",          "/finance?tab=sales"),
        ("accounting.expenses",  "Expenses",        "/finance?tab=expenses"),
        ("accounting.reports",   "Reports",         "/finance?tab=overview"),
        ("accounting.journals",  "Journal Entries", "/finance?tab=overview"),
    ]
    for codename, name, path in children:
        ModulePermission.objects.filter(codename=codename).update(name=name, path=path)

    # Add missing finance tabs if they don't exist yet
    parent = ModulePermission.objects.filter(codename="accounting").first()
    if parent:
        new_children = [
            ("finance.purchases", "finance", "Purchases",  "/finance?tab=purchases", 4),
            ("finance.banking",   "finance", "Banking",    "/finance?tab=banking",   5),
            ("finance.pettycash", "finance", "Petty Cash", "/finance?tab=pettycash", 6),
            ("finance.tax",       "finance", "Tax",        "/finance?tab=tax",       7),
        ]
        for codename, module_slug, name, path, sort_order in new_children:
            ModulePermission.objects.get_or_create(
                codename=codename,
                defaults={
                    "module_slug": module_slug,
                    "name": name,
                    "path": path,
                    "icon_slug": "",
                    "parent": parent,
                    "sort_order": sort_order,
                },
            )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("Authentication", "0012_bootstrap_module_permissions"),
    ]

    operations = [
        migrations.RunPython(rename_accounting_to_finance, noop),
    ]
