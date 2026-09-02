import os
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import Customer
from catalog.models import Product


class Command(BaseCommand):
    help = "Create missing deterministic local demonstration accounts and products."

    @transaction.atomic
    def handle(self, *args, **options):
        admin_password = os.getenv("DEMO_ADMIN_PASSWORD")
        customer_password = os.getenv("DEMO_CUSTOMER_PASSWORD")
        if not admin_password or not customer_password:
            raise CommandError(
                "Set DEMO_ADMIN_PASSWORD and DEMO_CUSTOMER_PASSWORD before running seed_demo."
            )

        user_model = get_user_model()
        admin, admin_created = user_model.objects.get_or_create(
            email="admin@tradeflow.local",
            defaults={"is_staff": True, "is_superuser": True, "is_active": True},
        )
        if admin_created:
            admin.set_password(admin_password)
            admin.save(update_fields=["password"])

        account_specs = (
            ("standard@tradeflow.local", "Acme Retail", Customer.Tier.STANDARD),
            ("wholesale@tradeflow.local", "Bulk Bazaar", Customer.Tier.WHOLESALE),
        )
        for email, company_name, tier in account_specs:
            user, user_created = user_model.objects.get_or_create(email=email)
            if user_created:
                user.set_password(customer_password)
                user.save(update_fields=["password"])
            Customer.objects.get_or_create(
                user=user,
                defaults={"company_name": company_name, "tier": tier},
            )

        product_specs = (
            ("SKU-A", "Product A", Decimal("100.00"), 100),
            ("SKU-B", "Product B", Decimal("250.00"), 75),
            ("SKU-C", "Product C", Decimal("499.99"), 25),
        )
        for sku, name, price, stock_quantity in product_specs:
            Product.objects.get_or_create(
                sku=sku,
                defaults={
                    "name": name,
                    "description": f"Demonstration catalog item {name}.",
                    "price": price,
                    "stock_quantity": stock_quantity,
                    "is_active": True,
                },
            )

        self.stdout.write(self.style.SUCCESS("Missing demo accounts and products are ready."))
