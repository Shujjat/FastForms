"""
Preset validation for short_text / paragraph answers (format key on Question.validation).

Uses Django validators where appropriate; phone uses a practical digit-count check (not full E.164).
"""

import re

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import EmailValidator, URLValidator

_EMAIL = EmailValidator()
_URL = URLValidator(schemes=("http", "https"))


def validate_text_format(value: str, fmt: str) -> None:
    """
    Raise ValueError with a short user-facing message if value fails the format.
    Empty/whitespace-only values are skipped (handled by required / min_length).
    """
    if not fmt:
        return
    s = "" if value is None else str(value).strip()
    if not s:
        return

    if fmt == "email":
        try:
            _EMAIL(s)
        except DjangoValidationError:
            raise ValueError("Enter a valid email address.") from None

    elif fmt == "phone":
        digits = re.sub(r"\D", "", s)
        if not (8 <= len(digits) <= 15):
            raise ValueError("Enter a valid phone number (8–15 digits, optional + and separators).")

    elif fmt == "url":
        u = s.strip()
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", u):
            u = "https://" + u
        try:
            _URL(u)
        except DjangoValidationError:
            raise ValueError("Enter a valid URL (e.g. https://example.com or example.com).") from None

    elif fmt == "zip_us":
        if not re.fullmatch(r"\d{5}(-\d{4})?", s):
            raise ValueError("Use US ZIP format: 12345 or 12345-6789.")

    elif fmt == "integer":
        if not re.fullmatch(r"-?\d+", s):
            raise ValueError("Enter a whole number (optional leading minus).")

    elif fmt == "alphanumeric":
        if not re.fullmatch(r"[a-zA-Z0-9]+", s):
            raise ValueError("Use letters and numbers only (no spaces).")
