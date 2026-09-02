import hashlib
import json
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone

from accounts.models import Customer
from catalog.models import Product
from orders.emails import send_order_confirmation
from orders.exceptions import OrderConflictError, OrderServiceError
from orders.models import Order, OrderItem

MONEY_QUANTUM = Decimal("0.01")
WHOLESALE_DISCOUNT_RATE = Decimal("0.1000")
WHOLESALE_QUANTITY_THRESHOLD = 50


def _money(value):
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def _canonical_items(items):
    return sorted(
        (
            {
                "product_id": int(item["product_id"]),
                "quantity": int(item["quantity"]),
            }
            for item in items
        ),
        key=lambda item: item["product_id"],
    )


def _request_hash(items):
    payload = json.dumps(_canonical_items(items), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


@transaction.atomic
def create_order(*, customer_id, items, idempotency_key):
    customer = Customer.objects.select_for_update().select_related("user").get(pk=customer_id)
    canonical_items = _canonical_items(items)
    if not canonical_items:
        raise OrderServiceError("empty_order", "An order must contain at least one product.")
    product_ids = [item["product_id"] for item in canonical_items]
    if len(product_ids) != len(set(product_ids)):
        raise OrderServiceError(
            "duplicate_product",
            "Each product may appear only once in an order.",
        )
    if not idempotency_key or len(idempotency_key) > 128:
        raise OrderServiceError(
            "invalid_idempotency_key",
            "A non-empty idempotency key of at most 128 characters is required.",
        )
    payload_hash = _request_hash(canonical_items)

    existing = Order.objects.filter(
        customer=customer,
        idempotency_key=idempotency_key,
    ).first()
    if existing:
        if existing.request_hash != payload_hash:
            raise OrderConflictError(
                "idempotency_conflict",
                "This idempotency key was already used with a different order payload.",
            )
        return existing, True

    locked_products = list(
        Product.objects.select_for_update().filter(id__in=product_ids).order_by("id")
    )
    products = {product.id: product for product in locked_products}

    missing_ids = sorted(set(product_ids) - set(products))
    if missing_ids:
        raise OrderServiceError(
            "product_not_found",
            "One or more requested products do not exist.",
            errors={"product_ids": missing_ids},
        )

    inactive_ids = [product_id for product_id in product_ids if not products[product_id].is_active]
    if inactive_ids:
        raise OrderServiceError(
            "product_unavailable",
            "One or more requested products are inactive.",
            errors={"product_ids": inactive_ids},
        )

    insufficient = [
        {
            "product_id": item["product_id"],
            "requested": item["quantity"],
            "available": products[item["product_id"]].stock_quantity,
        }
        for item in canonical_items
        if products[item["product_id"]].stock_quantity < item["quantity"]
    ]
    if insufficient:
        raise OrderConflictError(
            "insufficient_stock",
            "The order cannot be fulfilled because stock is insufficient.",
            errors={"products": insufficient},
        )

    subtotal = Decimal("0.00")
    item_snapshots = []
    for item in canonical_items:
        product = products[item["product_id"]]
        line_subtotal = _money(product.price * item["quantity"])
        subtotal += line_subtotal
        item_snapshots.append((product, item["quantity"], line_subtotal))
    subtotal = _money(subtotal)

    total_quantity = sum(item["quantity"] for item in canonical_items)
    discount_rate = (
        WHOLESALE_DISCOUNT_RATE
        if customer.tier == Customer.Tier.WHOLESALE
        and total_quantity >= WHOLESALE_QUANTITY_THRESHOLD
        else Decimal("0.0000")
    )
    discount_amount = _money(subtotal * discount_rate)
    total = _money(subtotal - discount_amount)

    order = Order.objects.create(
        customer=customer,
        subtotal=subtotal,
        discount_rate=discount_rate,
        discount_amount=discount_amount,
        total=total,
        idempotency_key=idempotency_key,
        request_hash=payload_hash,
    )
    OrderItem.objects.bulk_create(
        [
            OrderItem(
                order=order,
                product=product,
                product_sku=product.sku,
                product_name=product.name,
                unit_price=product.price,
                quantity=quantity,
                line_subtotal=line_subtotal,
            )
            for product, quantity, line_subtotal in item_snapshots
        ]
    )

    updated_at = timezone.now()
    for product, quantity, _line_subtotal in item_snapshots:
        product.stock_quantity -= quantity
        product.updated_at = updated_at
    Product.objects.bulk_update(locked_products, ["stock_quantity", "updated_at"])

    def send_confirmation():
        send_order_confirmation(order.id)

    transaction.on_commit(send_confirmation, robust=True)
    return order, False


@transaction.atomic
def cancel_order(*, order_id, actor_id):
    order = Order.objects.select_for_update().get(pk=order_id)
    if order.status == Order.Status.CANCELLED:
        return order, True

    items = list(order.items.order_by("product_id"))
    product_ids = [item.product_id for item in items]
    locked_products = list(
        Product.objects.select_for_update().filter(id__in=product_ids).order_by("id")
    )
    products = {product.id: product for product in locked_products}
    updated_at = timezone.now()
    for item in items:
        product = products[item.product_id]
        product.stock_quantity += item.quantity
        product.updated_at = updated_at
    Product.objects.bulk_update(locked_products, ["stock_quantity", "updated_at"])

    order.status = Order.Status.CANCELLED
    order.cancelled_by_id = actor_id
    order.cancelled_at = updated_at
    order.save(update_fields=["status", "cancelled_by", "cancelled_at", "updated_at"])
    return order, False
