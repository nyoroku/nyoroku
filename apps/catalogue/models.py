import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings


class Category(models.Model):
    """Top-level product grouping (e.g., Personal Care, Beverages, Groceries)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    icon = models.CharField(max_length=10, default='📦')
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'name']
        verbose_name_plural = 'Categories'

    def __str__(self):
        return self.name


class SubCategory(models.Model):
    """Second-level grouping within a Category (e.g., Bathing, Hair Care)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='subcategories')
    name = models.CharField(max_length=100)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'name']
        unique_together = [('category', 'name')]
        verbose_name_plural = 'Sub-categories'

    def __str__(self):
        return f"{self.category.name} → {self.name}"


class Product(models.Model):
    """
    Central product model with multi-sell-mode support.

    A product has one base unit and can optionally support three additional
    sell modes (split/pieces, weight, bunch) — independently activated
    via boolean checkboxes.
    """

    SPLIT_INVENTORY_CHOICES = [
        ('FIXED_CUT', 'Fixed Cut'),
        ('OPEN_CUT', 'Open Cut'),
    ]
    WEIGHT_UNIT_CHOICES = [
        ('kg', 'Kilograms'),
        ('g', 'Grams'),
        ('litre', 'Litres'),
        ('ml', 'Millilitres'),
    ]
    WEIGHT_SELL_MODE_CHOICES = [
        ('BY_WEIGHT', 'By Weight (cashier types kg)'),
        ('BY_CASH', 'By Cash (cashier types KES)'),
    ]

    # ── Identity ──
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    subcategory = models.ForeignKey(SubCategory, on_delete=models.CASCADE, related_name='products')
    sku = models.CharField(max_length=50, unique=True, blank=True)
    barcode = models.CharField(max_length=50, blank=True, default='')
    image = models.CharField(max_length=10, default='📦')

    # ── Base Unit Pricing ──
    base_unit_label = models.CharField(max_length=30, default='Unit')
    base_unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    # ── Split Sell Mode (Pieces) ──
    split_enabled = models.BooleanField(default=False, help_text='Can this product be sold in pieces?')
    split_unit_label = models.CharField(max_length=30, default='Piece', blank=True)
    split_unit_price = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text='Price per piece — set freely by admin, NEVER derived from base price',
    )
    pieces_per_base = models.IntegerField(
        default=1,
        help_text='Reference cut size per base unit (e.g., 8 pieces per bar)',
    )
    split_min_qty = models.IntegerField(default=1, help_text='Minimum pieces per transaction')
    split_inventory_mode = models.CharField(
        max_length=10, choices=SPLIT_INVENTORY_CHOICES, default='FIXED_CUT',
    )

    # ── Kadogo Sell Mode (Fractional) ──
    is_kadogo = models.BooleanField(default=False, help_text='Enable cutting whole units into fragments')
    whole_unit_label = models.CharField(max_length=30, default='Bar', help_text='Label for the whole unit (e.g., Bar, Packet)')
    whole_unit_stock = models.IntegerField(default=0, help_text='Count of uncut whole units available')

    # ── Weight Sell Mode ──
    weight_sell_enabled = models.BooleanField(default=False, help_text='Sell by weight')
    weight_unit = models.CharField(max_length=10, choices=WEIGHT_UNIT_CHOICES, default='kg')
    price_per_weight_unit = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text='Selling price per weight unit (e.g., KES 150/kg)',
    )
    stock_in_weight_unit = models.DecimalField(
        max_digits=12, decimal_places=3, default=Decimal('0.000'),
        help_text='Current on-hand stock in weight units (e.g., 25.750 kg)',
    )
    weight_sell_mode = models.CharField(
        max_length=10, choices=WEIGHT_SELL_MODE_CHOICES, default='BY_WEIGHT',
    )
    min_weight_increment = models.DecimalField(
        max_digits=12, decimal_places=3, default=Decimal('0.050'),
        help_text='Smallest sellable weight (e.g., 0.050 kg = 50g)',
    )
    reorder_threshold_weight = models.DecimalField(
        max_digits=12, decimal_places=3, null=True, blank=True,
    )

    # ── Unit of Measure & Bundle Pricing (UoM) ──
    purchase_unit_label = models.CharField(max_length=20, default='unit')
    units_per_purchase = models.PositiveIntegerField(default=1, help_text='1 = no conversion')
    bundle_pricing_enabled = models.BooleanField(default=False)
    bundle_qty = models.PositiveIntegerField(default=1, help_text='Base units per bundle. Must be >= 2 when enabled.')
    bundle_price = models.DecimalField(
        max_digits=12, decimal_places=2, default=0.00,
        help_text='Price per bundle in KES',
    )
    allow_single_sale = models.BooleanField(default=False, help_text='Allow selling < 1 bundle')
    single_unit_price = models.DecimalField(
        max_digits=12, decimal_places=2, default=0.00,
        help_text='Price per base unit when selling singles',
    )

    # ── Stock (base units) ──
    stock_qty = models.DecimalField(
        max_digits=12, decimal_places=3, default=Decimal('0'),
        help_text='On-hand stock in base units',
    )
    reorder_threshold = models.IntegerField(default=5)
    reorder_qty = models.IntegerField(default=10)

    # ── Supplier & Margin ──
    preferred_supplier = models.ForeignKey(
        'procurement.Supplier',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='preferred_products',
    )
    desired_margin_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text='Target gross margin as %',
    )
    desired_margin_kes = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text='Target gross margin in KES per base unit',
    )

    # ── Status ──
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='created_products',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                models.functions.Lower('name'),
                name='unique_product_name_ci',
            )
        ]

    def save(self, *args, **kwargs):
        # Auto-generate SKU if blank
        if not self.sku:
            prefix = self.name[:3].upper().replace(' ', '')
            import random
            self.sku = f"{prefix}-{random.randint(1000, 9999)}"
        super().save(*args, **kwargs)

    @property
    def effective_stock(self):
        """Stock in the relevant unit for display: weight for weight-sell, whole units for Kadogo, base units otherwise."""
        if self.weight_sell_enabled:
            return self.stock_in_weight_unit
        if self.is_kadogo:
            return self.whole_unit_stock
        return self.stock_qty

    @property
    def is_low_stock(self):
        if self.weight_sell_enabled and self.reorder_threshold_weight:
            return self.stock_in_weight_unit <= self.reorder_threshold_weight
        if self.is_kadogo:
            return self.whole_unit_stock <= self.reorder_threshold
        return self.stock_qty <= self.reorder_threshold

    @property
    def gross_margin_pct(self):
        """Current gross margin based on base_unit_price and cost_price."""
        if self.base_unit_price and self.cost_price and self.base_unit_price > 0:
            return round(
                (self.base_unit_price - self.cost_price) / self.base_unit_price * 100, 2
            )
        return None

    @property
    def total_kadogo_pieces(self):
        """Total possible fragments (in pool + potential from whole units)."""
        if not self.is_kadogo:
            return 0
        total = 0
        for frag in self.fragment_sizes.all():
            total += frag.fragment_pool + (self.whole_unit_stock * frag.fragment_count)
        return total

    @property
    def bundle_margin_pct(self):
        """Gross margin when sold in a bundle."""
        if self.bundle_pricing_enabled and self.bundle_price > 0 and self.cost_price:
            bundle_cost = self.cost_price * self.bundle_qty
            return round((self.bundle_price - bundle_cost) / self.bundle_price * 100, 2)
        return None

    def compute_bundle_total(self, qty):
        """Calculate total price for a given quantity in pieces, applying bundle logic if enabled."""
        if not self.bundle_pricing_enabled or not self.bundle_qty or not self.bundle_price:
            return self.base_unit_price * qty

        full_bundles = qty // self.bundle_qty
        remainder = qty % self.bundle_qty
        total = full_bundles * self.bundle_price
        
        if remainder > 0:
            if self.allow_single_sale and self.single_unit_price:
                total += remainder * self.single_unit_price
            else:
                # Pro-rate the bundle price as a fallback
                total += remainder * (self.bundle_price / self.bundle_qty)
        return total

    def __str__(self):
        return self.name


class Batch(models.Model):
    """Tracks stock at batch level for FEFO rotation and recall management."""

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('quarantined', 'Quarantined'),
        ('disposed', 'Disposed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='batches')
    batch_number = models.CharField(max_length=100)
    expiry_date = models.DateField(null=True, blank=True)
    quantity = models.DecimalField(
        max_digits=12, decimal_places=3,
        help_text='Current on-hand quantity for this batch',
    )
    received_date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['expiry_date', 'received_date']

    def __str__(self):
        exp = self.expiry_date.strftime('%Y-%m-%d') if self.expiry_date else 'No expiry'
        return f"{self.product.name} — Batch {self.batch_number} (exp: {exp})"

    @property
    def is_expired(self):
        if not self.expiry_date:
            return False
        from django.utils import timezone
        return self.expiry_date < timezone.now().date()

    @property
    def days_until_expiry(self):
        if not self.expiry_date:
            return None
        from django.utils import timezone
        delta = self.expiry_date - timezone.now().date()
        return delta.days

class FragmentSize(models.Model):
    """Defines a specific fractional size for a kadogo product (e.g., Half, Quarter)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='fragment_sizes')
    name = models.CharField(max_length=40)
    fragment_count = models.PositiveIntegerField(help_text='Number of fragments per whole unit (e.g., 7 for a 7-piece cut)')
    fragment_price = models.DecimalField(max_digits=12, decimal_places=2)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    fragment_pool = models.IntegerField(default=0, help_text='Current available fragments of this size')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('product', 'name')]

    def __str__(self):
        return f"{self.product.name} — {self.name} (KES {self.fragment_price})"


class CutAction(models.Model):
    """Audit record for a physical cutting event."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='cut_actions')
    fragment_size = models.ForeignKey(FragmentSize, on_delete=models.PROTECT)
    whole_units_cut = models.PositiveIntegerField(default=1)
    fragments_added = models.PositiveIntegerField()
    
    batch = models.ForeignKey('Batch', on_delete=models.SET_NULL, null=True, blank=True)
    performed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    performed_at = models.DateTimeField(auto_now_add=True)
    
    # Traceability
    TRIGGER_CHOICES = [('SALE', 'Sale Triggered'), ('MANUAL', 'Manual Pre-cut')]
    triggered_by = models.CharField(max_length=10, choices=TRIGGER_CHOICES, default='MANUAL')
    sale_reference = models.CharField(max_length=100, blank=True, default='')

    def __str__(self):
        return f"Cut {self.whole_units_cut} {self.product.name} into {self.fragments_added} {self.fragment_size.name}s"

class StockLedger(models.Model):
    """
    Append-only stock movement ledger tracking all inventory changes in base units.
    Implements the PRD requirements for UoM and Bundle Pricing.
    """
    ENTRY_TYPE_CHOICES = [
        ('SALE', 'Sale'),
        ('GRN', 'Goods Received Note'),
        ('ADJUSTMENT', 'Manual Adjustment'),
        ('VOID', 'Void / Refund'),
        ('CUT', 'Stock Cutting Action'),
    ]

    POOL_CHOICES = [
        ('WHOLE', 'Whole Unit Pool'),
        ('FRAGMENT', 'Fragment Pool'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='ledger_entries')
    entry_type = models.CharField(max_length=20, choices=ENTRY_TYPE_CHOICES)
    
    # Core inventory tracking (Base Units)
    qty_delta = models.IntegerField(help_text='Signed integer in base units (- for sales, + for receipts)')
    
    # Bundle Sale Snapshots (Populated on SALE/VOID)
    bundle_qty_sold = models.PositiveIntegerField(null=True, blank=True, help_text='Number of bundles in a SALE entry')
    bundle_size_snapshot = models.PositiveIntegerField(null=True, blank=True, help_text='Bundle Qty value at time of sale')
    bundle_price_snapshot = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text='Bundle Price at time of sale')
    is_singles_sale = models.BooleanField(default=False, help_text='True if this sale line used per-unit pricing')
    unit_label_snapshot = models.CharField(max_length=30, blank=True, default='')
    batch_snapshot = models.CharField(max_length=100, blank=True, default='', help_text='Batch Number snapshot')

    # GRN Snapshots (Populated on GRN)
    purchase_unit_qty = models.PositiveIntegerField(null=True, blank=True)
    purchase_unit_label_snapshot = models.CharField(max_length=30, blank=True, default='')
    # Kadogo tracking
    pool = models.CharField(max_length=10, choices=POOL_CHOICES, default='WHOLE')
    fragment_size = models.ForeignKey(FragmentSize, on_delete=models.SET_NULL, null=True, blank=True)
    fragment_size_snapshot = models.CharField(max_length=40, blank=True, default='')
    cut_action_id = models.UUIDField(null=True, blank=True)

    # Tracing & Audit
    reference_id = models.CharField(max_length=100, blank=True, default='', help_text='Sale ID, GRN ID, etc.')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.entry_type}] {self.product.name} ({self.qty_delta})"
