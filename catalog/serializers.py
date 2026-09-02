from rest_framework import serializers

from catalog.models import Product


class ProductSerializer(serializers.ModelSerializer):
    is_available = serializers.BooleanField(read_only=True)
    currency = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            "id",
            "sku",
            "name",
            "description",
            "price",
            "currency",
            "stock_quantity",
            "is_available",
            "updated_at",
        )
        read_only_fields = fields

    def get_currency(self, obj) -> str:
        return "INR"
