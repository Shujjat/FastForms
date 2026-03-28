from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()

_PUBLIC_ROLES = ("creator", "respondent")


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8, required=True)
    username = serializers.CharField(required=True, max_length=150)
    email = serializers.EmailField(required=True)
    role = serializers.ChoiceField(choices=[(r, r) for r in _PUBLIC_ROLES], required=True)
    first_name = serializers.CharField(required=False, allow_blank=True, default="")
    last_name = serializers.CharField(required=False, allow_blank=True, default="")
    phone = serializers.CharField(required=False, allow_blank=True, default="", max_length=32)
    organization = serializers.CharField(required=False, allow_blank=True, default="", max_length=255)

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "password",
            "role",
            "first_name",
            "last_name",
            "phone",
            "organization",
        )
        read_only_fields = ("id",)

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "role",
            "first_name",
            "last_name",
            "phone",
            "organization",
        )


class GoogleAuthSerializer(serializers.Serializer):
    credential = serializers.CharField(required=True, trim_whitespace=False)
    role = serializers.ChoiceField(choices=[(r, r) for r in _PUBLIC_ROLES], required=False, default="respondent")
