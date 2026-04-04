import uuid
from django.db import models
from django.conf import settings

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
    # Format: [{"id": "...", "name": "...", "qty": 1, "price": 100.00, "total": 100.00}, ...]
    items = models.JSONField()
    
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    
    payment_method = models.CharField(max_length=10, choices=PAYMENT_CHOICES, default='cash')
    mpesa_ref = models.CharField(max_length=100, null=True, blank=True)
    
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='complete')
    receipt_number = models.CharField(max_length=20, unique=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            # Generate a simple receipt number
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
