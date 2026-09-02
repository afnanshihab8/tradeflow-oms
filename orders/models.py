import uuid

from django.conf import settings
from django.db import models
from django.db.models import F, Q


class Order(models.Model):
    class Status(models.TextChoices):
        PLACED = "PLACED", "Placed"
        CANCELLED = "CANCELLED", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        "accounts.Customer",
        on_delete=models.PROTECT,
        related_name="orders",
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PLACED)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2)
    discount_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    discount_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=14, decimal_places=2)
    idempotency_key = models.CharField(max_length=128)
    request_hash = models.CharField(max_length=64)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="cancelled_orders",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["customer", "idempotency_key"],
                name="orders_customer_idempotency_unique",
            ),
            models.CheckConstraint(condition=Q(subtotal__gte=0), name="orders_subtotal_gte_zero"),
            models.CheckConstraint(
                condition=Q(discount_rate__gte=0) & Q(discount_rate__lte=1),
                name="orders_discount_rate_valid",
            ),
            models.CheckConstraint(
                condition=Q(discount_amount__gte=0),
                name="orders_discount_amount_gte_zero",
            ),
            models.CheckConstraint(condition=Q(total__gte=0), name="orders_total_gte_zero"),
            models.CheckConstraint(
                condition=Q(total__lte=F("subtotal")),
                name="orders_total_lte_subtotal",
            ),
        ]
        indexes = [
            models.Index(fields=["customer", "-created_at"], name="order_customer_created_idx"),
            models.Index(fields=["status", "-created_at"], name="order_status_created_idx"),
        ]

    def __str__(self):
        return f"Order {self.id} ({self.status})"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.PROTECT,
        related_name="order_items",
    )
    product_sku = models.CharField(max_length=64)
    product_name = models.CharField(max_length=255)
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    quantity = models.PositiveIntegerField()
    line_subtotal = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["order", "product"],
                name="orders_item_order_product_unique",
            ),
            models.CheckConstraint(
                condition=Q(quantity__gt=0),
                name="orders_item_quantity_gt_zero",
            ),
            models.CheckConstraint(
                condition=Q(unit_price__gt=0),
                name="orders_item_unit_price_gt_zero",
            ),
            models.CheckConstraint(
                condition=Q(line_subtotal__gt=0),
                name="orders_item_line_subtotal_gt_zero",
            ),
        ]

    def __str__(self):
        return f"{self.quantity} × {self.product_sku}"
