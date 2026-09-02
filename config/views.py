from django.db import connection
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthStatusSerializer(serializers.Serializer):
    status = serializers.CharField()
    database = serializers.CharField()


class HealthCheckView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)

    @extend_schema(
        responses={status.HTTP_200_OK: HealthStatusSerializer},
        tags=["System"],
        description="Confirm that the API and its PostgreSQL connection are available.",
    )
    def get(self, request):
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")

        return Response({"status": "ok", "database": "ok"})
