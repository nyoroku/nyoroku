import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone


class Sale(models.Model):
    """A completed or pending point-of-sale transaction."""

    PAYMENT_CHOICES = [
        ('cash', 'Cash'),
        ('mpesa', 'M-Pesa'),
        ('split', 'Split (Cash + M-Pesa)'),
        ('credit', 'Credit / Tab'),
    ]
    STATUS_CHOICES = [
        ('complete', 'Complete'),
        ('voided', 'Voided'),
        ('pending_payment', 'Pending Payment'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    receipt_number = models.CharField(max_length=20, unique=True)

    cashier = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='sales',
    )

    # ── Totals ──
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    discount_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    vat_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    total = models.DecimalField(max_digits=12, decimal_places=2)

    # ── Payment ──
    payment_method = models.CharField(max_length=10, choices=PAYMENT_CHOICES, default='cash')
    cash_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    cash_tendered = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    change_due = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    mpesa_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    mpesa_phone = models.CharField(max_length=15, blank=True, default='')
    mpesa_reference = models.CharField(max_length=100, blank=True, default='')
    mpesa_stk_checkout_id = models.CharField(max_length=100, blank=True, default='')

    # ── Credit ──
    credit_customer_name = models.CharField(max_length=200, blank=True, default='')
    credit_due_date = models.DateField(null=True, blank=True)

    # ── Status ──
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='complete')
    created_at = models.DateTimeField(auto_now_add=True)

    # ── Void ──
    void_reason = models.TextField(blank=True, default='')
    voided_at = models.DateTimeField(null=True, blank=True)
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='voided_sales',
    )

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            year = timezone.now().strftime('%Y')
            last = Sale.objects.filter(
                receipt_number__startswith=f'FLK-{year}-'
            ).order_by('-receipt_number').first()
            if last:
                try:
                    last_num = int(last.receipt_number.split('-')[-1])
                    self.receipt_number = f"FLK-{year}-{last_num + 1:05d}"
                except (ValueError, IndexError):
                    self.receipt_number = f"FLK-{year}-00001"
            else:
                self.receipt_number = f"FLK-{year}-00001"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.receipt_number


class SaleLineItem(models.Model):
    """Individual item line within a sale, tracking sell mode and deductions."""

    SELL_MODE_CHOICES = [
        ('whole', 'Whole Unit'),
        ('split', 'Split / Pieces'),
        ('weight', 'Weight'),
        ('bundle', 'Bundle'),
        ('single', 'Singles'),
        ('hamper', 'Hamper'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='line_items')
    product = models.ForeignKey(
        'catalogue.Product', on_delete=models.PROTECT,
        related_name='sale_lines',
    )
    product_name = models.CharField(max_length=200)  # Snapshot at sale time

    # ── Sell mode ──
    sell_mode = models.CharField(max_length=10, choices=SELL_MODE_CHOICES, default='whole')

    # ── Pricing ──
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)

    # ── Bundle Snapshots (PRD 8.1) ──
    bundle_size_snapshot = models.PositiveIntegerField(null=True, blank=True)
    bundle_price_snapshot = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    is_singles_sale = models.BooleanField(default=False)

    # ── Weight details (when sell_mode = 'weight') ──
    weight_value = models.DecimalField(
        max_digits=12, decimal_places=3, null=True, blank=True,
        help_text='Weight sold (e.g., 1.333 kg)',
    )
    weight_unit = models.CharField(max_length=10, blank=True, default='')

    # ── Promotion ──
    promotion = models.ForeignKey(
        'promotions.Promotion', on_delete=models.SET_NULL,
        null=True, blank=True,
    )
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    is_free_item = models.BooleanField(default=False, help_text='BOGOF free items')

    # ── Batch (FEFO tracking) ──
    batch = models.ForeignKey(
        'catalogue.Batch', on_delete=models.SET_NULL,
        null=True, blank=True,
    )

    # ── Cost snapshot for margin reporting ──
    cost_price_at_sale = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
    )

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.product_name} × {self.quantity}"


class ParkedSale(models.Model):
    """A sale that has been parked (saved for later) by a cashier."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cashier = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='parked_sales',
    )
    customer_identifier = models.CharField(max_length=50, blank=True, default='')
    items = models.JSONField(default=list)
    parked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-parked_at']

    def __str__(self):
        return f"Parked by {self.cashier} at {self.parked_at.strftime('%H:%M')}"
