import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin

class UserManager(BaseUserManager):
    def create_user(self, pin, name, role='cashier', **extra_fields):
        if not pin:
            raise ValueError('The PIN must be set')
        user = self.model(pin=pin, name=name, role=role, **extra_fields)
        # PIN is stored as bcrypt hash via AbstractBaseUser's set_password mechanism
        user.set_password(pin) 
        user.save(using=self._db)
        return user

    def create_superuser(self, pin, name, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(pin, name, role='admin', **extra_fields)

class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('cashier', 'Cashier'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='cashier')
    # pin is handled by AbstractBaseUser.password
    avatar = models.CharField(max_length=2, default='👤') 
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = 'id' # We identify by UUID in session
    REQUIRED_FIELDS = ['name']

    def __str__(self):
        return f"{self.name} ({self.role})"
