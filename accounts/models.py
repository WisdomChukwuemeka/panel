from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils import timezone
import uuid


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, agreement=False, full_name=None, role='participant', **extra_fields):
        if not email:
            raise ValueError("Users must have an email address")

        # Normalize email
        email = self.normalize_email(email)

        # Default active users
        extra_fields.setdefault('is_active', True)

        # Role-based permissions
        if role == 'admin':
            extra_fields.setdefault('is_staff', True)
            extra_fields.setdefault('is_superuser', True)
        elif role == 'publisher':
            extra_fields.setdefault('is_staff', True)
            extra_fields.setdefault('is_superuser', False)
        elif role == 'editor':
            extra_fields.setdefault('is_staff', True)
            extra_fields.setdefault('is_superuser', False)
        else:  # participant
            extra_fields.setdefault('is_staff', False)
            extra_fields.setdefault('is_superuser', False)
        
        if not agreement:
            raise ValueError("Users must agree to the terms and conditions to register.")   
                    
        user = self.model(email=email, full_name=full_name, agreement=agreement, role=role, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, full_name=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_superuser', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError("is_superuser must be set to is_staff=True")
        if extra_fields.get('is_superuser') is not True:
            raise ValueError("is_superuser must be set to is_superuser=True")
        return self.create_user(email, password, **extra_fields)
    


class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('publisher', 'Publisher'),
        ('editor', 'Editor'),
        ('reader', 'Reader'),
    )

    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=255, null=True, blank=True)
    role = models.CharField(max_length=32, choices=ROLE_CHOICES, default='reader')
    agreement = models.BooleanField(default=False)
    # permissions
    is_superuser = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_passcode_verified = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_scholar = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.full_name or self.email
    
    def get_full_name(self):
        return self.full_name or self.email



class Passcode(models.Model):
    code = models.CharField(max_length=50, unique=True, blank=True)
    role = models.CharField(max_length=50, choices=User.ROLE_CHOICES)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='generated_codes')
    is_used = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.code} - {self.role}"