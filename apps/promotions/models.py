import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone


class Promotion(models.Model):
    """Active promotion — only one can apply to a product at a time."""

    PROMO_TYPE_CHOICES = [
        ('bogof', 'Buy One Get One Free'),
        ('multi_unit', 'Multi-Unit Deal'),
        ('pct_discount', 'Percentage Discount'),
        ('fixed_discount', 'Fixed Amount Off'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    promo_type = models.CharField(max_length=15, choices=PROMO_TYPE_CHOICES)

    # Target — either a specific product or an entire category
    product = models.ForeignKey(
        'catalogue.Product', on_delete=models.CASCADE,
        null=True, blank=True, related_name='promotions',
    )
    category = models.ForeignKey(
        'catalogue.Category', on_delete=models.CASCADE,
        null=True, blank=True, related_name='promotions',
    )

    # ── BOGOF config ──
    buy_qty = models.IntegerField(null=True, blank=True, help_text='Buy N items')
    free_qty = models.IntegerField(null=True, blank=True, help_text='Get M free')

    # ── Multi-unit deal ──
    deal_qty = models.IntegerField(null=True, blank=True, help_text='e.g., 3 for KES 5')
    deal_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    # ── Percentage / Fixed discount ──
    discount_pct = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    # ── Date range (mandatory) ──
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    @property
    def is_currently_active(self):
        now = timezone.now()
        return self.is_active and self.start_date <= now <= self.end_date

    @property
    def badge_text(self):
        """Short text for POS badges."""
        if self.promo_type == 'bogof':
            return f"Buy {self.buy_qty} Get {self.free_qty} FREE"
        elif self.promo_type == 'multi_unit':
            return f"{self.deal_qty} for KES {self.deal_price}"
        elif self.promo_type == 'pct_discount':
            return f"{self.discount_pct}% OFF"
        elif self.promo_type == 'fixed_discount':
            return f"KES {self.discount_amount} OFF"
        return 'PROMO'

    def __str__(self):
        return f"{self.name} ({self.get_promo_type_display()})"


class Hamper(models.Model):
    """Curated bundle of products sold as a single SKU at a composite price."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    sku = models.CharField(max_length=50, unique=True)
    barcode = models.CharField(max_length=50, blank=True, default='')
    image = models.CharField(max_length=10, default='🎁')
    price = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text='Fixed composite selling price',
    )
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    @property
    def component_total(self):
        """Sum of individual component prices."""
        total = Decimal('0')
        for comp in self.components.all():
            if comp.use_split and comp.product.split_unit_price:
                total += comp.product.split_unit_price * comp.quantity
            else:
                total += comp.product.base_unit_price * comp.quantity
        return total

    @property
    def implied_discount(self):
        """Discount implied by the hamper price vs sum of components."""
        return self.component_total - self.price

    @property
    def is_available(self):
        """Check if all component products have sufficient stock."""
        for comp in self.components.all():
            if comp.product.stock_qty < comp.quantity:
                return False
        return True

    def __str__(self):
        return self.name


class HamperComponent(models.Model):
    """One product within a hamper."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hamper = models.ForeignKey(Hamper, on_delete=models.CASCADE, related_name='components')
    product = models.ForeignKey(
        'catalogue.Product', on_delete=models.PROTECT,
        related_name='hamper_components',
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    use_split = models.BooleanField(
        default=False,
        help_text='Use split unit instead of whole base unit',
    )

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.product.name} × {self.quantity}"
