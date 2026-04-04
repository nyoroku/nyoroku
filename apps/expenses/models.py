import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone

class Expense(models.Model):
    CATEGORY_CHOICES = (
        ('stock', 'Stock'),
        ('utilities', 'Utilities'),
        ('staff', 'Staff'),
        ('transport', 'Transport'),
        ('rent', 'Rent'),
        ('other', 'Other'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    note = models.TextField(blank=True, null=True)
    
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='recorded_expenses'
    )
    
    date = models.DateField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.amount}"
