from django.db import models
from django.db.models import Q


class Product(models.Model):
    sku = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=14, decimal_places=2)
    stock_quantity = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]
        constraints = [
            models.CheckConstraint(condition=Q(price__gt=0), name="catalog_product_price_gt_zero"),
            models.CheckConstraint(
                condition=Q(stock_quantity__gte=0),
                name="catalog_product_stock_gte_zero",
            ),
        ]
        indexes = [models.Index(fields=["is_active", "name"], name="product_active_name_idx")]

    @property
    def is_available(self):
        return self.is_active and self.stock_quantity > 0

    def deactivate(self):
        self.is_active = False
        self.save(update_fields=["is_active", "updated_at"])

    def __str__(self):
        return f"{self.sku} — {self.name}"
