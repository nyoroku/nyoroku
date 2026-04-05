import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone

class Coupon(models.Model):
    DISCOUNT_TYPE_CHOICES = (
        ('fixed', 'Fixed Amount'),
        ('percent', 'Percentage'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=30, unique=True)
    description = models.CharField(max_length=200, blank=True, default='')
    discount_type = models.CharField(max_length=10, choices=DISCOUNT_TYPE_CHOICES, default='fixed')
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    min_order = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, 
                                      help_text='Minimum order amount required')
    max_uses = models.IntegerField(null=True, blank=True, help_text='Max total uses, leave blank for unlimited')
    used_count = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    valid_from = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_coupons')
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.code = self.code.upper().strip()
        super().save(*args, **kwargs)

    @property
    def is_valid(self):
        now = timezone.now()
        if not self.is_active:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        if now < self.valid_from:
            return False
        if self.max_uses and self.used_count >= self.max_uses:
            return False
        return True

    @property
    def display_value(self):
        if self.discount_type == 'percent':
            return f"{self.discount_value}%"
        return f"KES {self.discount_value}"

    def __str__(self):
        return f"{self.code} ({self.display_value})"


class ParkedSale(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cashier = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='parked_sales')
    customer_identifier = models.CharField(max_length=50, blank=True, help_text="Optional name or tag for the parked sale")
    items = models.JSONField(default=list)
    parked_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-parked_at']
        
    def __str__(self):
        return f"Parked by {self.cashier} at {self.parked_at.strftime('%Y-%m-%d %H:%M')}"


class Transaction(models.Model):
    PAYMENT_CHOICES = (
        ('cash', 'Cash'),
        ('mpesa', 'M-Pesa'),
        ('card', 'Card'),
    )
    
    STATUS_CHOICES = (
        ('complete', 'Complete'),
        ('voided', 'Voided'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cashier = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='transactions')
    
    # Store items snapshot as JSON
    items = models.JSONField()
    
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    coupon = models.ForeignKey(Coupon, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    coupon_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    
    payment_method = models.CharField(max_length=10, choices=PAYMENT_CHOICES, default='cash')
    mpesa_ref = models.CharField(max_length=100, null=True, blank=True)
    
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='complete')
    receipt_number = models.CharField(max_length=20, unique=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            last_transaction = Transaction.objects.all().order_by('created_at').last()
            if last_transaction:
                try:
                    last_num = int(last_transaction.receipt_number.split('-')[-1])
                    self.receipt_number = f"REC-{last_num + 1:06d}"
                except (ValueError, IndexError):
                    self.receipt_number = f"REC-000001"
            else:
                self.receipt_number = "REC-000001"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.receipt_number
