from decimal import Decimal

from django.core.management.base import BaseCommand

from Payments.models.individual_billing import IndividualSubscriptionPlan


class Command(BaseCommand):
    help = "Create default individual subscription plans"

    def handle(self, *args, **options):
        plans = [
            {
                "tier": "starter",
                "name": "Starter Plan",
                "description": "Perfect for freelancers and small businesses just getting started",
                "monthly_price_kes": Decimal("1500.00"),
                "features": {
                    "invoices": 50,
                    "transactions": 100,
                    "users": 1,
                    "reports": "basic",
                    "support": "email",
                },
                "max_transactions": 100,
                "max_invoices": 50,
            },
            {
                "tier": "professional",
                "name": "Professional Plan",
                "description": "For growing businesses that need more features and capacity",
                "monthly_price_kes": Decimal("3500.00"),
                "features": {
                    "invoices": 200,
                    "transactions": 500,
                    "users": 3,
                    "reports": "advanced",
                    "support": "priority_email",
                    "api_access": True,
                },
                "max_transactions": 500,
                "max_invoices": 200,
            },
            {
                "tier": "business",
                "name": "Business Plan",
                "description": "Comprehensive solution for established businesses",
                "monthly_price_kes": Decimal("7500.00"),
                "features": {
                    "invoices": 1000,
                    "transactions": 2000,
                    "users": 10,
                    "reports": "advanced",
                    "support": "phone_email",
                    "api_access": True,
                    "custom_branding": True,
                },
                "max_transactions": 2000,
                "max_invoices": 1000,
            },
            {
                "tier": "enterprise",
                "name": "Enterprise Plan",
                "description": "Unlimited features for large organizations",
                "monthly_price_kes": Decimal("15000.00"),
                "features": {
                    "invoices": -1,
                    "transactions": -1,
                    "users": -1,
                    "reports": "custom",
                    "support": "dedicated",
                    "api_access": True,
                    "custom_branding": True,
                    "white_label": True,
                    "sla": "99.9%",
                },
                "max_transactions": -1,
                "max_invoices": -1,
            },
        ]

        for plan_data in plans:
            plan, created = IndividualSubscriptionPlan.objects.update_or_create(
                tier=plan_data["tier"],
                defaults=plan_data,
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f"Created plan: {plan.name}")
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f"Updated plan: {plan.name}")
                )

        self.stdout.write(
            self.style.SUCCESS("Successfully created/updated all individual plans")
        )
