from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    email = serializers.EmailField(write_only=True)
    password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        style={"input_type": "password"},
    )

    def validate(self, attrs):
        attrs["email"] = attrs["email"].strip().lower()
        return super().validate(attrs)


class TokenPairResponseSerializer(serializers.Serializer):
    access = serializers.CharField(read_only=True)
    refresh = serializers.CharField(read_only=True)


class AuthenticationErrorSerializer(serializers.Serializer):
    code = serializers.CharField(read_only=True)
    detail = serializers.CharField(read_only=True)
    errors = serializers.DictField(read_only=True, allow_null=True)
