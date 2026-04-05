import uuid
from django.db import models
from django.conf import settings

class Category(models.Model):
    name = models.CharField(max_length=50, unique=True)
    
    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name

class Product(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    stock_qty = models.IntegerField(default=0)
    reorder_level = models.IntegerField(default=5)
    has_variants = models.BooleanField(default=False)
    barcode = models.CharField(max_length=100, blank=True, unique=True, null=True)
    image = models.CharField(max_length=10, default='📦') # Emoji string
    
    approved = models.BooleanField(default=False)
    pending_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='pending_products'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.barcode:
            # Generate a simple barcode if empty
            self.barcode = str(uuid.uuid4().int)[:12]
        super().save(*args, **kwargs)

    @property
    def total_stock(self):
        if self.has_variants:
            from django.db.models import Sum
            return self.variants.aggregate(Sum('stock_qty'))['stock_qty__sum'] or 0
        return self.stock_qty

    @property
    def variants_json(self):
        import json
        if not self.has_variants:
            return "[]"
        vs = []
        for v in self.variants.filter(stock_qty__gt=0):
            vs.append({
                'id': str(v.id),
                'name': v.name,
                'options': list(v.options.values()),
                'price': float(v.price),
                'stock_qty': v.stock_qty,
            })
        return json.dumps(vs)

    def __str__(self):
        return self.name

class ProductVariantOptionType(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='option_types')
    name = models.CharField(max_length=50) # e.g. "Size", "Colour"
    values = models.JSONField(default=list) # e.g. ["S", "M", "L"]

    def __str__(self):
        return f"{self.product.name} - {self.name}"

class ProductVariant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    options = models.JSONField(default=dict) # e.g. {"Size": "M", "Colour": "Red"}
    
    price_override = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    stock_qty = models.IntegerField(default=0)
    reorder_level = models.IntegerField(default=5)
    barcode = models.CharField(max_length=100, blank=True, unique=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.barcode:
            self.barcode = str(uuid.uuid4().int)[:12]
        super().save(*args, **kwargs)

    @property
    def price(self):
        return self.price_override if self.price_override is not None else self.product.price

    @property
    def get_cost_price(self):
        return self.cost_price if self.cost_price is not None else self.product.cost_price

    @property
    def name(self):
        options_str = " / ".join(str(v) for v in self.options.values())
        if options_str:
            return f"{self.product.name} ({options_str})"
        return self.product.name

    def __str__(self):
        return self.name

class PendingAction(models.Model):
    ACTION_CHOICES = (
        ('stock_adjustment', 'Stock Adjustment'),
        ('purchase_order', 'Purchase Order'),
        ('grn', 'Goods Receiving Note'),
        ('stock_transfer', 'Stock Transfer'),
        ('void_transaction', 'Void Transaction'),
    )
    STATUS_CHOICES = (
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    action_type = models.CharField(max_length=20, choices=ACTION_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='submitted_actions')
    submitted_at = models.DateTimeField(auto_now_add=True)
    
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_actions')
    approved_at = models.DateTimeField(null=True, blank=True)
    
    rejection_reason = models.TextField(blank=True, null=True)
    details = models.JSONField(default=dict) # {"product_id": x, "variant_id": y, "qty": z, "notes": "..."}
    
    def __str__(self):
        return f"{self.get_action_type_display()} - {self.get_status_display()}"
