import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.contrib.auth.hashers import make_password, check_password as django_check_password

PROFILE_COLORS = [
    '#00C853', '#7C4DFF', '#FFB300', '#FF1744', '#00B0FF',
    '#FF6D00', '#D500F9', '#1DE9B6', '#F50057', '#00E5FF',
]

class UserManager(BaseUserManager):
    def create_user(self, username, pin, name, role='cashier', **extra_fields):
        if not username:
            raise ValueError('The Username must be set')
        if not pin:
            raise ValueError('The PIN must be set')
        user = self.model(username=username, name=name, role=role, **extra_fields)
        user.set_password(pin) 
        # Also store the hashed PIN
        user.pin_hash = make_password(str(pin))
        user.save(using=self._db)
        return user

    def create_superuser(self, username, pin, name, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(username, pin, name, role='admin', **extra_fields)

class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('cashier', 'Cashier'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='cashier')
    avatar = models.CharField(max_length=2, default='👤') 
    color = models.CharField(max_length=10, default='#00C853')
    pin_hash = models.CharField(max_length=128, blank=True, default='')
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['name', 'pin']

    def set_pin(self, raw_pin):
        """Set the user's 4-digit PIN (hashed)."""
        self.pin_hash = make_password(str(raw_pin))

    def check_pin(self, raw_pin):
        """Check the user's 4-digit PIN."""
        return django_check_password(str(raw_pin), self.pin_hash)

    def save(self, *args, **kwargs):
        # Assign a random profile color if not set
        if not self.color or self.color == '#00C853':
            import random
            self.color = random.choice(PROFILE_COLORS)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} (@{self.username})"
