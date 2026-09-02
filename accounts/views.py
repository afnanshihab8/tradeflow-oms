from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.views import (
    TokenBlacklistView,
    TokenObtainPairView,
    TokenRefreshView,
)

from accounts.serializers import (
    AuthenticationErrorSerializer,
    EmailTokenObtainPairSerializer,
    TokenPairResponseSerializer,
)


@extend_schema(
    tags=["Authentication"],
    request=EmailTokenObtainPairSerializer,
    responses={
        200: TokenPairResponseSerializer,
        400: AuthenticationErrorSerializer,
        401: AuthenticationErrorSerializer,
    },
)
class EmailTokenObtainPairView(TokenObtainPairView):
    permission_classes = [AllowAny]
    serializer_class = EmailTokenObtainPairSerializer


@extend_schema(tags=["Authentication"])
class RefreshTokenView(TokenRefreshView):
    permission_classes = [AllowAny]


@extend_schema(tags=["Authentication"])
class BlacklistTokenView(TokenBlacklistView):
    permission_classes = [AllowAny]
