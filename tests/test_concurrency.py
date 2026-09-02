from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier

import pytest
from django.core import mail
from django.db import close_old_connections

from accounts.models import Customer, User
from catalog.models import Product
from orders.exceptions import OrderServiceError
from orders.models import Order
from orders.services import cancel_order, create_order

pytestmark = pytest.mark.django_db(transaction=True)


def make_customer(index):
    user = User.objects.create_user(
        email=f"race-{index}@example.com",
        password="CustomerPass!2026",
    )
    return Customer.objects.create(user=user, company_name=f"Race Customer {index}")


def test_concurrent_customers_cannot_oversell_last_unit():
    customers = [make_customer(1), make_customer(2)]
    product = Product.objects.create(
        sku="LAST-UNIT",
        name="Last Unit",
        price=Decimal("50.00"),
        stock_quantity=1,
    )
    barrier = Barrier(2)

    def submit(customer_id, key):
        close_old_connections()
        try:
            barrier.wait(timeout=5)
            order, _replayed = create_order(
                customer_id=customer_id,
                items=[{"product_id": product.id, "quantity": 1}],
                idempotency_key=key,
            )
            return "created", str(order.id)
        except OrderServiceError as exc:
            return exc.code, None
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                lambda args: submit(*args),
                [(customers[0].id, "race-1"), (customers[1].id, "race-2")],
            )
        )

    assert sorted(result[0] for result in results) == ["created", "insufficient_stock"]
    product.refresh_from_db()
    assert product.stock_quantity == 0
    assert Order.objects.count() == 1


def test_concurrent_identical_submissions_create_one_order_and_one_email():
    customer = make_customer(3)
    product = Product.objects.create(
        sku="IDEMPOTENT-RACE",
        name="Idempotent Race",
        price=Decimal("30.00"),
        stock_quantity=5,
    )
    barrier = Barrier(2)

    def submit():
        close_old_connections()
        try:
            barrier.wait(timeout=5)
            order, replayed = create_order(
                customer_id=customer.id,
                items=[{"product_id": product.id, "quantity": 2}],
                idempotency_key="same-concurrent-key",
            )
            return str(order.id), replayed
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _index: submit(), range(2)))

    assert results[0][0] == results[1][0]
    assert sorted(result[1] for result in results) == [False, True]
    assert Order.objects.count() == 1
    product.refresh_from_db()
    assert product.stock_quantity == 3
    assert len(mail.outbox) == 1


def test_concurrent_cancellation_restores_stock_once():
    customer = make_customer(4)
    product = Product.objects.create(
        sku="CANCEL-RACE",
        name="Cancellation Race",
        price=Decimal("20.00"),
        stock_quantity=5,
    )
    order, _replayed = create_order(
        customer_id=customer.id,
        items=[{"product_id": product.id, "quantity": 2}],
        idempotency_key="cancel-race-order",
    )
    mail.outbox.clear()
    barrier = Barrier(2)

    def cancel():
        close_old_connections()
        try:
            barrier.wait(timeout=5)
            _order, already_cancelled = cancel_order(
                order_id=order.id,
                actor_id=customer.user_id,
            )
            return already_cancelled
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _index: cancel(), range(2)))

    assert sorted(results) == [False, True]
    product.refresh_from_db()
    order.refresh_from_db()
    assert product.stock_quantity == 5
    assert order.status == Order.Status.CANCELLED
