# core/utils/validators.py
from django.core.exceptions import ValidationError


def validate_phone(value):
    if len(value) < 10:
        raise ValidationError("Phone number must be at least 10 digits.")
    if not value.isdigit():
        raise ValidationError("Phone number must contain only digits.")


def validate_email(value):
    if "@" not in value:
        raise ValidationError("Email must contain @ symbol.")
    if "." not in value:
        raise ValidationError("Email must contain . symbol.")


# core/utils/formatters.py
def format_phone(value):
    return f"+{value[:3]}-{value[3:6]}-{value[6:]}"


def format_email(value):
    return value.lower()


# core/utils/formatters.py
def format_phone(value):
    return f"+{value[:3]}-{value[3:6]}-{value[6:]}"


def format_email(value):
    return value.lower()


# core/utils/formatters.py
def format_phone(value):
    return f"+{value[:3]}-{value[3:6]}-{value[6:]}"


def format_email(value):
    return value.lower()
