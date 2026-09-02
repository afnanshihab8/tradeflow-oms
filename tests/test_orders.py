from decimal import Decimal

import pytest
from django.core import mail
from rest_framework import status

from accounts.models import Customer, User
from orders.models import Order

pytestmark = pytest.mark.django_db


def post_order(client, items, key="order-key-1"):
    return client.post(
        "/api/v1/orders/",
        {"items": items},
        format="json",
        HTTP_IDEMPOTENCY_KEY=key,
    )


def test_customer_places_atomic_multi_product_order_and_receives_email(
    authenticated_client,
    customer_user,
    customer,
    product,
    second_product,
    django_capture_on_commit_callbacks,
):
    client = authenticated_client(customer_user)
    with django_capture_on_commit_callbacks(execute=True):
        response = post_order(
            client,
            [
                {"product_id": product.id, "quantity": 10},
                {"product_id": second_product.id, "quantity": 2},
            ],
        )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["subtotal"] == "1500.00"
    assert response.data["discount_amount"] == "0.00"
    assert response.data["total"] == "1500.00"
    assert len(response.data["items"]) == 2
    product.refresh_from_db()
    second_product.refresh_from_db()
    assert product.stock_quantity == 90
    assert second_product.stock_quantity == 98
    assert Order.objects.count() == 1
    assert len(mail.outbox) == 1
    assert customer_user.email in mail.outbox[0].to


def test_insufficient_stock_rolls_back_every_product(
    authenticated_client,
    customer_user,
    customer,
    product,
    second_product,
    django_capture_on_commit_callbacks,
):
    product.stock_quantity = 10
    product.save(update_fields=["stock_quantity"])
    second_product.stock_quantity = 1
    second_product.save(update_fields=["stock_quantity"])

    with django_capture_on_commit_callbacks(execute=True):
        response = post_order(
            authenticated_client(customer_user),
            [
                {"product_id": product.id, "quantity": 5},
                {"product_id": second_product.id, "quantity": 2},
            ],
        )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.data["code"] == "insufficient_stock"
    assert Order.objects.count() == 0
    product.refresh_from_db()
    second_product.refresh_from_db()
    assert product.stock_quantity == 10
    assert second_product.stock_quantity == 1
    assert len(mail.outbox) == 0


def test_order_validation_rejects_missing_inactive_and_duplicate_products(
    authenticated_client,
    customer_user,
    customer,
    product,
):
    client = authenticated_client(customer_user)
    missing = post_order(client, [{"product_id": 999999, "quantity": 1}], "missing")
    assert missing.status_code == status.HTTP_400_BAD_REQUEST
    assert missing.data["code"] == "product_not_found"

    product.deactivate()
    inactive = post_order(client, [{"product_id": product.id, "quantity": 1}], "inactive")
    assert inactive.status_code == status.HTTP_400_BAD_REQUEST
    assert inactive.data["code"] == "product_unavailable"

    duplicate = post_order(
        client,
        [
            {"product_id": product.id, "quantity": 1},
            {"product_id": product.id, "quantity": 2},
        ],
        "duplicate",
    )
    assert duplicate.status_code == status.HTTP_400_BAD_REQUEST
    assert Order.objects.count() == 0


def test_missing_and_oversized_idempotency_keys_are_rejected(
    authenticated_client,
    customer_user,
    customer,
    product,
):
    client = authenticated_client(customer_user)
    missing = client.post(
        "/api/v1/orders/",
        {"items": [{"product_id": product.id, "quantity": 1}]},
        format="json",
    )
    assert missing.status_code == status.HTTP_400_BAD_REQUEST
    assert missing.data["code"] == "missing_idempotency_key"

    oversized = post_order(
        client,
        [{"product_id": product.id, "quantity": 1}],
        "x" * 129,
    )
    assert oversized.status_code == status.HTTP_400_BAD_REQUEST
    assert oversized.data["code"] == "invalid_idempotency_key"


def test_idempotent_retry_returns_existing_order_without_side_effects(
    authenticated_client,
    customer_user,
    customer,
    product,
    django_capture_on_commit_callbacks,
):
    client = authenticated_client(customer_user)
    payload = [{"product_id": product.id, "quantity": 3}]
    with django_capture_on_commit_callbacks(execute=True):
        first = post_order(client, payload, "same-key")
    with django_capture_on_commit_callbacks(execute=True):
        replay = post_order(client, payload, "same-key")

    assert first.status_code == status.HTTP_201_CREATED
    assert replay.status_code == status.HTTP_200_OK
    assert replay["Idempotent-Replayed"] == "true"
    assert replay.data["id"] == first.data["id"]
    assert Order.objects.count() == 1
    product.refresh_from_db()
    assert product.stock_quantity == 97
    assert len(mail.outbox) == 1


def test_idempotency_key_reuse_with_different_payload_returns_conflict(
    authenticated_client,
    customer_user,
    customer,
    product,
):
    client = authenticated_client(customer_user)
    first = post_order(client, [{"product_id": product.id, "quantity": 1}], "conflict-key")
    second = post_order(client, [{"product_id": product.id, "quantity": 2}], "conflict-key")

    assert first.status_code == status.HTTP_201_CREATED
    assert second.status_code == status.HTTP_409_CONFLICT
    assert second.data["code"] == "idempotency_conflict"
    product.refresh_from_db()
    assert product.stock_quantity == 99


def test_price_and_product_snapshots_survive_catalog_changes(
    authenticated_client,
    customer_user,
    customer,
    product,
):
    client = authenticated_client(customer_user)
    created = post_order(client, [{"product_id": product.id, "quantity": 2}], "snapshot")
    product.name = "Renamed Widget"
    product.price = Decimal("120.00")
    product.save(update_fields=["name", "price"])

    detail = client.get(f"/api/v1/orders/{created.data['id']}/")
    assert detail.status_code == status.HTTP_200_OK
    assert detail.data["items"][0]["product_name"] == "Widget"
    assert detail.data["items"][0]["unit_price"] == "100.00"
    assert detail.data["total"] == "200.00"


@pytest.mark.parametrize(
    ("tier", "quantity", "expected_rate", "expected_discount", "expected_total"),
    [
        (Customer.Tier.STANDARD, 50, "0.0000", "0.00", "5000.00"),
        (Customer.Tier.WHOLESALE, 49, "0.0000", "0.00", "4900.00"),
        (Customer.Tier.WHOLESALE, 50, "0.1000", "500.00", "4500.00"),
    ],
)
def test_discount_boundary(
    authenticated_client,
    customer_user,
    customer,
    product,
    tier,
    quantity,
    expected_rate,
    expected_discount,
    expected_total,
):
    customer.tier = tier
    customer.save(update_fields=["tier"])
    response = post_order(
        authenticated_client(customer_user),
        [{"product_id": product.id, "quantity": quantity}],
        f"discount-{tier}-{quantity}",
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["discount_rate"] == expected_rate
    assert response.data["discount_amount"] == expected_discount
    assert response.data["total"] == expected_total


def test_customer_order_scope_and_staff_review_and_cancel(
    authenticated_client,
    customer_user,
    customer,
    other_user,
    other_customer,
    staff_user,
    product,
):
    created = post_order(
        authenticated_client(customer_user),
        [{"product_id": product.id, "quantity": 4}],
        "permissions",
    )
    order_url = f"/api/v1/orders/{created.data['id']}/"

    other_detail = authenticated_client(other_user).get(order_url)
    assert other_detail.status_code == status.HTTP_404_NOT_FOUND
    assert authenticated_client(other_user).get("/api/v1/orders/").data["count"] == 0

    staff_client = authenticated_client(staff_user)
    staff_list = staff_client.get(f"/api/v1/orders/?customer_id={customer.id}")
    assert staff_list.status_code == status.HTTP_200_OK
    assert staff_list.data["count"] == 1
    assert staff_client.get(order_url).status_code == status.HTTP_200_OK
    invalid_filter = staff_client.get("/api/v1/orders/?customer_id=not-an-integer")
    assert invalid_filter.status_code == status.HTTP_400_BAD_REQUEST

    cancelled = staff_client.post(f"{order_url}cancel/")
    assert cancelled.status_code == status.HTTP_200_OK
    assert cancelled.data["status"] == Order.Status.CANCELLED
    product.refresh_from_db()
    assert product.stock_quantity == 100


def test_staff_and_users_without_customer_profiles_cannot_use_customer_operations(
    authenticated_client,
    staff_user,
    product,
    db,
):
    staff_client = authenticated_client(staff_user)
    payload = [{"product_id": product.id, "quantity": 1}]
    staff_create = post_order(staff_client, payload, "staff-create")
    assert staff_create.status_code == status.HTTP_403_FORBIDDEN
    assert staff_client.get("/api/v1/orders/summary/").status_code == status.HTTP_403_FORBIDDEN

    orphan = User.objects.create_user(email="orphan@example.com", password="CustomerPass!2026")
    orphan_client = authenticated_client(orphan)
    assert orphan_client.get("/api/v1/orders/").status_code == status.HTTP_403_FORBIDDEN
    orphan_create = post_order(orphan_client, payload, "orphan-create")
    assert orphan_create.status_code == status.HTTP_403_FORBIDDEN


def test_cancellation_is_idempotent_and_restores_stock_once(
    authenticated_client,
    customer_user,
    customer,
    product,
):
    client = authenticated_client(customer_user)
    created = post_order(client, [{"product_id": product.id, "quantity": 7}], "cancel")
    cancel_url = f"/api/v1/orders/{created.data['id']}/cancel/"

    first = client.post(cancel_url)
    second = client.post(cancel_url)

    assert first.status_code == status.HTTP_200_OK
    assert second.status_code == status.HTTP_200_OK
    assert second["Idempotent-Replayed"] == "true"
    product.refresh_from_db()
    assert product.stock_quantity == 100


def test_summary_excludes_cancelled_orders_and_handles_zero_orders(
    authenticated_client,
    customer_user,
    customer,
    product,
    second_product,
):
    client = authenticated_client(customer_user)
    zero = client.get("/api/v1/orders/summary/")
    assert zero.data == {
        "order_count": 0,
        "total_spent": "0.00",
        "average_order_value": "0.00",
        "currency": "INR",
    }

    first = post_order(client, [{"product_id": product.id, "quantity": 1}], "summary-1")
    second = post_order(client, [{"product_id": second_product.id, "quantity": 2}], "summary-2")
    client.post(f"/api/v1/orders/{second.data['id']}/cancel/")

    summary = client.get("/api/v1/orders/summary/")
    assert summary.status_code == status.HTTP_200_OK
    assert summary.data == {
        "order_count": 1,
        "total_spent": "100.00",
        "average_order_value": "100.00",
        "currency": "INR",
    }
    assert first.data["status"] == Order.Status.PLACED


def test_email_failure_after_commit_does_not_change_successful_order_response(
    authenticated_client,
    customer_user,
    customer,
    product,
    django_capture_on_commit_callbacks,
    monkeypatch,
):
    def fail_email(order_id):
        raise RuntimeError("simulated email outage")

    monkeypatch.setattr("orders.services.send_order_confirmation", fail_email)
    with django_capture_on_commit_callbacks(execute=True):
        response = post_order(
            authenticated_client(customer_user),
            [{"product_id": product.id, "quantity": 1}],
            "email-failure",
        )

    assert response.status_code == status.HTTP_201_CREATED
    assert Order.objects.filter(pk=response.data["id"]).exists()
