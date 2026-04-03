"""Limit OpenAPI schema to integration-facing routes (Public API v1 + API key management)."""


def filter_public_endpoints(endpoints):
    """Keep only /api/v1/* and /api/auth/api-keys* for external documentation."""
    kept = []
    for path, path_regex, method, callback in endpoints:
        p = path or ""
        if p.startswith("/api/v1/") or p.startswith("/api/auth/api-keys"):
            kept.append((path, path_regex, method, callback))
    return kept


def add_security_to_documented_paths(result, generator, request, public):
    """Attach OpenAPI security requirements so Swagger UI shows Authorize correctly."""
    paths = result.get("paths") or {}
    http_ops = frozenset({"get", "post", "put", "patch", "delete", "head", "options"})

    for path_key, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method, op in path_item.items():
            if method not in http_ops or not isinstance(op, dict):
                continue
            if path_key.startswith("/api/v1/"):
                op["security"] = [{"ApiKeyAuth": []}]
            elif path_key.startswith("/api/auth/api-keys"):
                op["security"] = [{"jwtAuth": []}]
    return result
