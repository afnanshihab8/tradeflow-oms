from rest_framework import serializers

from accounts.models import Customer
from orders.models import Order, OrderItem


class CustomerSummarySerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = Customer
        fields = ("id", "company_name", "tier", "email")
        read_only_fields = fields


class OrderItemInputSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1)


class OrderCreateSerializer(serializers.Serializer):
    items = OrderItemInputSerializer(many=True, allow_empty=False)

    def validate_items(self, items):
        product_ids = [item["product_id"] for item in items]
        if len(product_ids) != len(set(product_ids)):
            raise serializers.ValidationError("Each product may appear only once in an order.")
        return items


class OrderItemSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = OrderItem
        fields = (
            "product_id",
            "product_sku",
            "product_name",
            "unit_price",
            "quantity",
            "line_subtotal",
        )
        read_only_fields = fields


class OrderSerializer(serializers.ModelSerializer):
    customer = CustomerSummarySerializer(read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)
    currency = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = (
            "id",
            "customer",
            "status",
            "items",
            "subtotal",
            "discount_rate",
            "discount_amount",
            "total",
            "currency",
            "idempotency_key",
            "created_at",
            "cancelled_at",
        )
        read_only_fields = fields

    def get_currency(self, obj) -> str:
        return "INR"


class PurchasingSummarySerializer(serializers.Serializer):
    order_count = serializers.IntegerField()
    total_spent = serializers.DecimalField(max_digits=14, decimal_places=2)
    average_order_value = serializers.DecimalField(max_digits=14, decimal_places=2)
    currency = serializers.CharField()


class StaffOrderFilterSerializer(serializers.Serializer):
    customer_id = serializers.IntegerField(min_value=1, required=False)
    status = serializers.ChoiceField(choices=Order.Status.choices, required=False)
