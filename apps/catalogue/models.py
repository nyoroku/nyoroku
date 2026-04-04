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
    barcode = models.CharField(max_length=100, blank=True, unique=True)
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

    def __str__(self):
        return self.name
