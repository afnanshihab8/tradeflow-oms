from decimal import Decimal

from django.db.models import Avg, Count, Sum
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from orders.exceptions import OrderServiceError
from orders.models import Order
from orders.permissions import IsCustomerOnly, IsStaffOrCustomer
from orders.serializers import (
    OrderCreateSerializer,
    OrderSerializer,
    PurchasingSummarySerializer,
    StaffOrderFilterSerializer,
)
from orders.services import cancel_order, create_order


@extend_schema_view(
    list=extend_schema(
        tags=["Orders"],
        parameters=[
            OpenApiParameter(
                name="customer_id",
                type=int,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Staff only: filter orders by customer ID.",
            ),
            OpenApiParameter(
                name="status",
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                enum=Order.Status.values,
                description="Staff only: filter by PLACED or CANCELLED.",
            ),
        ],
    ),
    retrieve=extend_schema(tags=["Orders"]),
)
class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Order.objects.none()
    serializer_class = OrderSerializer

    def get_permissions(self):
        account_permission = (
            IsCustomerOnly if self.action in {"create", "summary"} else IsStaffOrCustomer
        )
        return [IsAuthenticated(), account_permission()]

    def get_queryset(self):
        queryset = Order.objects.select_related("customer__user").prefetch_related("items")
        user = self.request.user
        if user.is_staff:
            filters = StaffOrderFilterSerializer(data=self.request.query_params)
            filters.is_valid(raise_exception=True)
            customer_id = filters.validated_data.get("customer_id")
            order_status = filters.validated_data.get("status")
            if customer_id:
                queryset = queryset.filter(customer_id=customer_id)
            if order_status:
                queryset = queryset.filter(status=order_status)
            return queryset
        return queryset.filter(customer=user.customer)

    def get_serializer_class(self):
        if self.action == "create":
            return OrderCreateSerializer
        return OrderSerializer

    @extend_schema(
        tags=["Orders"],
        parameters=[
            OpenApiParameter(
                name="Idempotency-Key",
                type=str,
                location=OpenApiParameter.HEADER,
                required=True,
                description=(
                    "Unique key for this customer's semantic order request (max 128 chars)."
                ),
            )
        ],
        request=OrderCreateSerializer,
        responses={
            200: OrderSerializer,
            201: OrderSerializer,
            400: OpenApiResponse(description="Invalid payload or missing idempotency key"),
            409: OpenApiResponse(description="Insufficient stock or idempotency conflict"),
        },
    )
    def create(self, request, *args, **kwargs):
        idempotency_key = request.headers.get("Idempotency-Key", "").strip()
        if not idempotency_key:
            return Response(
                {
                    "code": "missing_idempotency_key",
                    "detail": "The Idempotency-Key header is required.",
                    "errors": {"Idempotency-Key": ["This header is required."]},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(idempotency_key) > 128:
            return Response(
                {
                    "code": "invalid_idempotency_key",
                    "detail": "The Idempotency-Key header must not exceed 128 characters.",
                    "errors": {"Idempotency-Key": ["Maximum length is 128 characters."]},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            order, replayed = create_order(
                customer_id=request.user.customer.id,
                items=serializer.validated_data["items"],
                idempotency_key=idempotency_key,
            )
        except OrderServiceError as exc:
            return Response(exc.as_response_data(), status=exc.status_code)

        order = self.get_queryset().get(pk=order.pk)
        response_status = status.HTTP_200_OK if replayed else status.HTTP_201_CREATED
        headers = {"Idempotent-Replayed": "true"} if replayed else {}
        return Response(
            OrderSerializer(order, context=self.get_serializer_context()).data,
            status=response_status,
            headers=headers,
        )

    @extend_schema(tags=["Orders"], request=None, responses={200: OrderSerializer})
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        order = self.get_object()
        _order, already_cancelled = cancel_order(order_id=order.pk, actor_id=request.user.pk)
        refreshed = self.get_queryset().get(pk=order.pk)
        headers = {"Idempotent-Replayed": "true"} if already_cancelled else {}
        return Response(
            OrderSerializer(refreshed, context=self.get_serializer_context()).data,
            headers=headers,
        )

    @extend_schema(tags=["Orders"], responses={200: PurchasingSummarySerializer})
    @action(detail=False, methods=["get"])
    def summary(self, request):
        aggregate = Order.objects.filter(
            customer=request.user.customer,
            status=Order.Status.PLACED,
        ).aggregate(
            order_count=Count("id"),
            total_spent=Sum("total"),
            average_order_value=Avg("total"),
        )
        data = {
            "order_count": aggregate["order_count"],
            "total_spent": aggregate["total_spent"] or Decimal("0.00"),
            "average_order_value": aggregate["average_order_value"] or Decimal("0.00"),
            "currency": "INR",
        }
        return Response(PurchasingSummarySerializer(data).data)
