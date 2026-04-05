import uuid
from django.db import models
from django.conf import settings

class Supplier(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class PurchaseOrder(models.Model):
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('partially_received', 'Partially Received'),
        ('received', 'Fully Received'),
        ('cancelled', 'Cancelled'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lpo_number = models.CharField(max_length=50, unique=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name='purchase_orders')
    
    expected_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Store items as JSON array: [{"product_id": x, "variant_id": (optional), "qty": 10, "unit_cost": 150}]
    items = models.JSONField(default=list)
    
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='submitted_pos')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_pos')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def total_cost(self):
        return sum(item.get('total_cost', 0) for item in self.items)

    def save(self, *args, **kwargs):
        if not self.lpo_number:
            last_po = PurchaseOrder.objects.all().order_by('created_at').last()
            if last_po:
                try:
                    last_num = int(last_po.lpo_number.split('-')[-1])
                    self.lpo_number = f"LPO-{last_num + 1:04d}"
                except (ValueError, IndexError):
                    self.lpo_number = "LPO-0001"
            else:
                self.lpo_number = "LPO-0001"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.lpo_number

class GoodsReceivingNote(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    po = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, related_name='grns')
    delivery_note_number = models.CharField(max_length=100, blank=True)
    
    # Received items JSON array: [{"product_id": x, "variant_id": (optional), "received_qty": 5}]
    received_items = models.JSONField(default=list)
    
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='received_grns')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"GRN for {self.po.lpo_number}"
