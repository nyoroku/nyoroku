import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings


class AuditTrail(models.Model):
    """Immutable, append-only audit trail for every data-modifying action in Floki."""

    ACTION_CHOICES = [
        ('sale_processed', 'Sale Processed'),
        ('sale_voided', 'Sale Voided / Refund'),
        ('price_changed', 'Product Price Changed'),
        ('stock_adjusted', 'Stock Adjusted (Manual)'),
        ('po_created', 'PO Created'),
        ('po_approved', 'PO Approved'),
        ('goods_received', 'Goods Received'),
        ('promotion_changed', 'Promotion Created / Edited / Deleted'),
        ('hamper_changed', 'Hamper Created / Edited'),
        ('audit_completed', 'Stock Audit Completed'),
        ('user_changed', 'User Created / Role Changed'),
        ('login', 'Login'),
        ('logout', 'Logout'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='audit_entries',
    )
    entity_type = models.CharField(max_length=50, blank=True, default='')
    entity_id = models.CharField(max_length=50, blank=True, default='')
    description = models.TextField(default='')
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Audit Trail Entry'
        verbose_name_plural = 'Audit Trail'

    def __str__(self):
        return f"[{self.get_action_display()}] {self.description[:80]}"


def log_audit(action, user=None, entity_type='', entity_id='',
              description='', metadata=None, ip_address=None):
    """Helper function to create an audit trail record."""
    AuditTrail.objects.create(
        action=action,
        user=user,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id else '',
        description=description,
        metadata=metadata or {},
        ip_address=ip_address,
    )
