from django.contrib import admin
from django.utils import timezone

from catalog.models import Product


@admin.action(description="Deactivate selected products")
def deactivate_products(modeladmin, request, queryset):
    queryset.update(is_active=False, updated_at=timezone.now())


@admin.action(description="Activate selected products")
def activate_products(modeladmin, request, queryset):
    queryset.update(is_active=True, updated_at=timezone.now())


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("sku", "name", "price", "stock_quantity", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("sku", "name", "description")
    actions = (deactivate_products, activate_products)

    def has_delete_permission(self, request, obj=None):
        return False
