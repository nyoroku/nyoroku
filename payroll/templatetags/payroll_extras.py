# payroll/templatetags/__init__.py
# Empty file to make this a Python package

# payroll/templatetags/payroll_extras.py

from django import template
from decimal import Decimal

register = template.Library()

@register.filter
def filter_by_type(adjustments, adjustment_type):
    """Filter adjustments by type (ALLOWANCE or DEDUCTION)"""
    return adjustments.filter(type=adjustment_type)

@register.filter
def sum_amounts(adjustments):
    """Sum the amounts of a queryset of adjustments"""
    total = sum(adj.amount for adj in adjustments)
    return Decimal(str(total))

@register.filter
def currency(value):
    """Format a number as currency"""
    try:
        return f"KSh {float(value):,.2f}"
    except (ValueError, TypeError):
        return "KSh 0.00"