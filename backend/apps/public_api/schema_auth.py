from drf_spectacular.extensions import OpenApiAuthenticationExtension


class ApiKeyAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "apps.public_api.authentication.ApiKeyAuthentication"
    name = "ApiKeyAuth"
    priority = -1

    def get_security_definition(self, auto_schema):
        return {
            "type": "apiKey",
            "in": "header",
            "name": "X-Api-Key",
            "description": "Secret from POST /api/auth/api-keys (shown once).",
        }
