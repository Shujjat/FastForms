"""Gravatar URLs for user photos (no uploaded avatars in this project)."""

import hashlib


def gravatar_url(email: str, *, size: int = 64) -> str:
    if not email or not str(email).strip():
        return f"https://www.gravatar.com/avatar/00000000000000000000000000000000?d=identicon&s={size}"
    h = hashlib.md5(email.strip().lower().encode("utf-8")).hexdigest()
    return f"https://www.gravatar.com/avatar/{h}?d=identicon&s={size}"
