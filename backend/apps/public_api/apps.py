from django.apps import AppConfig


class PublicApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.public_api"
    label = "public_api"
    verbose_name = "Public API (v1)"

    def ready(self):
        # Register OpenAPI extension for ApiKeyAuthentication (drf-spectacular).
        import apps.public_api.schema_auth  # noqa: F401
