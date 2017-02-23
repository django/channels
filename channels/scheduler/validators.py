import json

from django.core.exceptions import ValidationError


def validate_json_string(value):
    try:
        json.loads(value)
    except Exception:
        raise ValidationError('%s is not a valid JSON string' % value)
