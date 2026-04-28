import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings


class AuditSession(models.Model):
    """A random stock audit initiated by an admin."""

    SCOPE_CHOICES = [
        ('all', 'All Stock'),
        ('category', 'Category'),
        ('subcategory', 'Sub-Category'),
    ]
    STATUS_CHOICES = [
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='audit_sessions',
    )
    scope = models.CharField(max_length=15, choices=SCOPE_CHOICES, default='all')
    scope_category = models.ForeignKey(
        'catalogue.Category', on_delete=models.SET_NULL,
        null=True, blank=True,
    )
    scope_subcategory = models.ForeignKey(
        'catalogue.SubCategory', on_delete=models.SET_NULL,
        null=True, blank=True,
    )
    sample_size = models.IntegerField(default=10)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='in_progress')
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    @property
    def total_items(self):
        return self.items.count()

    @property
    def variance_count(self):
        return self.items.exclude(variance=Decimal('0')).exclude(variance__isnull=True).count()

    @property
    def match_count(self):
        return self.items.filter(variance=Decimal('0')).count()

    def __str__(self):
        return f"Audit #{str(self.id)[:8]} — {self.get_scope_display()} ({self.get_status_display()})"


class AuditItem(models.Model):
    """One product within an audit session — holds system qty vs physical count."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(AuditSession, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(
        'catalogue.Product', on_delete=models.PROTECT,
        related_name='audit_items',
    )
    system_qty = models.DecimalField(max_digits=12, decimal_places=3)
    physical_qty = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    variance = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    note = models.CharField(max_length=200, blank=True, default='')

    class Meta:
        ordering = ['product__name']

    @property
    def status_icon(self):
        if self.variance is None:
            return '⏳'
        if self.variance == 0:
            return '✅'
        if self.variance > 0:
            return '🔼'
        return '❌'

    def __str__(self):
        return f"{self.product.name}: system={self.system_qty}, physical={self.physical_qty}"
