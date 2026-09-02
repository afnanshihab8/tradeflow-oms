from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import filters, viewsets

from catalog.models import Product
from catalog.serializers import ProductSerializer


@extend_schema_view(
    list=extend_schema(tags=["Products"]),
    retrieve=extend_schema(tags=["Products"]),
)
class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ProductSerializer
    filter_backends = (filters.SearchFilter, filters.OrderingFilter)
    search_fields = ("sku", "name", "description")
    ordering_fields = ("name", "price", "stock_quantity")
    ordering = ("name", "id")

    def get_queryset(self):
        return Product.objects.filter(is_active=True)
