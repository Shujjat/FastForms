import hashlib
import secrets


def generate_api_key_material() -> tuple[str, str, str]:
    """Return (full_secret, prefix, sha256_hex)."""
    raw = f"ff_{secrets.token_urlsafe(32)}"
    prefix = raw[:12]
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return raw, prefix, digest
