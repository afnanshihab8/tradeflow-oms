from decimal import Decimal

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import Customer, User
from catalog.models import Product


@pytest.fixture(autouse=True)
def use_local_memory_email_backend(settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"


@pytest.fixture
def customer_user(db):
    return User.objects.create_user(email="buyer@example.com", password="CustomerPass!2026")


@pytest.fixture
def customer(customer_user):
    return Customer.objects.create(
        user=customer_user,
        company_name="Buyer Business",
        tier=Customer.Tier.STANDARD,
    )


@pytest.fixture
def wholesale_user(db):
    return User.objects.create_user(email="wholesale@example.com", password="CustomerPass!2026")


@pytest.fixture
def wholesale_customer(wholesale_user):
    return Customer.objects.create(
        user=wholesale_user,
        company_name="Wholesale Business",
        tier=Customer.Tier.WHOLESALE,
    )


@pytest.fixture
def other_user(db):
    return User.objects.create_user(email="other@example.com", password="CustomerPass!2026")


@pytest.fixture
def other_customer(other_user):
    return Customer.objects.create(
        user=other_user,
        company_name="Other Business",
        tier=Customer.Tier.STANDARD,
    )


@pytest.fixture
def staff_user(db):
    return User.objects.create_user(
        email="staff@example.com",
        password="StaffPass!2026",
        is_staff=True,
    )


@pytest.fixture
def product(db):
    return Product.objects.create(
        sku="SKU-001",
        name="Widget",
        description="A wholesale widget",
        price=Decimal("100.00"),
        stock_quantity=100,
    )


@pytest.fixture
def second_product(db):
    return Product.objects.create(
        sku="SKU-002",
        name="Gadget",
        description="A wholesale gadget",
        price=Decimal("250.00"),
        stock_quantity=100,
    )


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def authenticated_client():
    def build(user):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
        return client

    return build
