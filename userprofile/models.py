from django.db import models
from django.utils import timezone
from accounts.models import User
# Create your models here.

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.PROTECT, related_name='profile')    
    bio = models.TextField(blank=True)
    institution = models.CharField(max_length=40, blank=True, null=True)
    affiliation = models.CharField(max_length=255, blank=True)
    date_joined = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"{self.institution or 'No Institution'} – {self.bio[:20]}"