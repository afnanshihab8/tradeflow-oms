from django.contrib import admin

from orders.models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    readonly_fields = (
        "product",
        "product_sku",
        "product_name",
        "unit_price",
        "quantity",
        "line_subtotal",
    )

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "status", "total", "created_at", "cancelled_at")
    list_filter = ("status", "created_at")
    search_fields = ("id", "customer__company_name", "customer__user__email")
    list_select_related = ("customer", "customer__user")
    inlines = (OrderItemInline,)
    readonly_fields = (
        "id",
        "customer",
        "status",
        "subtotal",
        "discount_rate",
        "discount_amount",
        "total",
        "idempotency_key",
        "request_hash",
        "cancelled_at",
        "cancelled_by",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
