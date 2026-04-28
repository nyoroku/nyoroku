import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone


class Supplier(models.Model):
    """Supplier / vendor for purchasing goods."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=200, blank=True, default='')
    phone = models.CharField(max_length=50, blank=True, default='')
    email = models.EmailField(blank=True, default='')
    address = models.TextField(blank=True, default='')
    payment_terms = models.CharField(
        max_length=100, blank=True, default='',
        help_text='e.g., Net 30, Cash on Delivery, Pro-forma',
    )
    kra_pin = models.CharField(max_length=20, blank=True, default='', help_text='For VAT invoice matching')
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class PurchaseOrder(models.Model):
    """Purchase order to a supplier — normalised with line items."""

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending_approval', 'Pending Approval'),
        ('approved', 'Approved'),
        ('sent', 'Sent'),
        ('partially_received', 'Partially Received'),
        ('fully_received', 'Fully Received'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    po_number = models.CharField(max_length=20, unique=True)
    supplier = models.ForeignKey(
        Supplier, on_delete=models.PROTECT,
        related_name='purchase_orders',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    expected_delivery_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, default='')

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='created_pos',
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='approved_pos',
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.po_number:
            year = timezone.now().strftime('%Y')
            last = PurchaseOrder.objects.filter(
                po_number__startswith=f'PO-{year}-'
            ).order_by('-po_number').first()
            if last:
                try:
                    last_num = int(last.po_number.split('-')[-1])
                    self.po_number = f"PO-{year}-{last_num + 1:04d}"
                except (ValueError, IndexError):
                    self.po_number = f"PO-{year}-0001"
            else:
                self.po_number = f"PO-{year}-0001"
        super().save(*args, **kwargs)

    @property
    def total_cost(self):
        return sum(
            item.unit_cost * item.ordered_qty
            for item in self.line_items.all()
        )

    @property
    def is_fully_received(self):
        return all(
            item.line_status == 'received'
            for item in self.line_items.all()
        )

    @property
    def below_margin_count(self):
        """Count of line items below desired margin threshold."""
        count = 0
        for item in self.line_items.all():
            if item.product.desired_margin_pct and item.margin_at_order is not None:
                if item.margin_at_order < float(item.product.desired_margin_pct):
                    count += 1
        return count

    def __str__(self):
        return f"{self.po_number} — {self.supplier.name}"


class POLineItem(models.Model):
    """Individual line item on a purchase order."""

    LINE_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('partial', 'Partial'),
        ('received', 'Fully Received'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    po = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='line_items')
    product = models.ForeignKey(
        'catalogue.Product', on_delete=models.PROTECT,
        related_name='po_line_items',
    )
    ordered_qty = models.DecimalField(max_digits=12, decimal_places=3)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)
    received_qty = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal('0'))
    line_status = models.CharField(max_length=10, choices=LINE_STATUS_CHOICES, default='pending')

    # Batch info (entered at receipt time)
    batch_number = models.CharField(max_length=100, blank=True, default='')
    expiry_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['id']

    @property
    def line_total(self):
        return self.unit_cost * self.ordered_qty

    @property
    def remaining_qty(self):
        return self.ordered_qty - self.received_qty

    @property
    def margin_at_order(self):
        """Computed gross margin % based on product sell price and this PO's unit cost (converted to base)."""
        sell = self.product.base_unit_price
        # Derived unit cost = PO unit cost / units per purchase
        multiplier = self.product.units_per_purchase or 1
        derived_unit_cost = self.unit_cost / Decimal(str(multiplier))
        
        if sell and sell > 0:
            return round(float((sell - derived_unit_cost) / sell * 100), 2)
        return None

    @property
    def margin_kes(self):
        """Absolute margin in KES (per base unit)."""
        sell = self.product.base_unit_price
        multiplier = self.product.units_per_purchase or 1
        derived_unit_cost = self.unit_cost / Decimal(str(multiplier))
        if sell:
            return sell - derived_unit_cost
        return None

    @property
    def previous_order_cost(self):
        """Unit cost from the most recent previous PO for this product."""
        prev = POLineItem.objects.filter(
            product=self.product,
        ).exclude(
            po=self.po,
        ).order_by('-po__created_at').first()
        return prev.unit_cost if prev else None

    @property
    def margin_variance(self):
        """Returns 'good', 'warning', or 'danger' based on desired margin comparison."""
        desired = self.product.desired_margin_pct
        actual = self.margin_at_order
        if desired is None or actual is None:
            return 'neutral'
        if actual >= float(desired):
            return 'good'
        if actual >= float(desired) - 5:
            return 'warning'
        return 'danger'

    def __str__(self):
        return f"{self.product.name} × {self.ordered_qty}"


class GoodsReceipt(models.Model):
    """Record of a goods receipt event against a PO."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    po = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='receipts')
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='goods_receipts',
    )
    notes = models.TextField(blank=True, default='')
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-received_at']

    def __str__(self):
        return f"GR for {self.po.po_number} at {self.received_at.strftime('%Y-%m-%d %H:%M')}"


class GoodsReceiptItem(models.Model):
    """Individual line within a goods receipt."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    receipt = models.ForeignKey(GoodsReceipt, on_delete=models.CASCADE, related_name='items')
    po_line = models.ForeignKey(POLineItem, on_delete=models.PROTECT, related_name='receipt_items')
    received_qty = models.DecimalField(max_digits=12, decimal_places=3)
    batch_number = models.CharField(max_length=100, blank=True, default='')
    expiry_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.po_line.product.name} × {self.received_qty}"


class PurchaseOrderTrail(models.Model):
    """Activity log for a purchase order."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    po = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='trail')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=200)
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.po.po_number} — {self.action}"
