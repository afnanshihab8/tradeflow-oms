from decimal import Decimal

import pytest
from django.core.management import call_command

from accounts.models import Customer, User
from catalog.models import Product

pytestmark = pytest.mark.django_db


def test_repeated_demo_seed_does_not_overwrite_existing_business_state(monkeypatch):
    monkeypatch.setenv("DEMO_ADMIN_PASSWORD", "InitialAdmin!2026")
    monkeypatch.setenv("DEMO_CUSTOMER_PASSWORD", "InitialCustomer!2026")
    call_command("seed_demo")

    product = Product.objects.get(sku="SKU-A")
    product.stock_quantity = 7
    product.price = Decimal("135.50")
    product.save(update_fields=["stock_quantity", "price"])

    customer = Customer.objects.get(user__email="standard@tradeflow.local")
    customer.tier = Customer.Tier.WHOLESALE
    customer.save(update_fields=["tier"])

    user = User.objects.get(email="standard@tradeflow.local")
    user.set_password("ChangedCustomer!2026")
    user.save(update_fields=["password"])

    monkeypatch.setenv("DEMO_ADMIN_PASSWORD", "DifferentAdmin!2026")
    monkeypatch.setenv("DEMO_CUSTOMER_PASSWORD", "DifferentCustomer!2026")
    call_command("seed_demo")

    product.refresh_from_db()
    customer.refresh_from_db()
    user.refresh_from_db()
    assert product.stock_quantity == 7
    assert product.price == Decimal("135.50")
    assert customer.tier == Customer.Tier.WHOLESALE
    assert user.check_password("ChangedCustomer!2026")
