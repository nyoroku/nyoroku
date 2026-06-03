from django import template
from decimal import Decimal, InvalidOperation

register = template.Library()

@register.filter
def clean_qty(value):
    """Normalize a decimal quantity to remove trailing zeros (e.g. 1.0000 -> 1, 0.2500 -> 0.25)"""
    if value is None:
        return ""
    try:
        # Convert to string and strip trailing zeroes
        return Decimal(str(value)).normalize()
    except (InvalidOperation, TypeError, ValueError):
        return value
