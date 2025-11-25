from django.db import models
from django.utils import timezone
from accounts.models import User
from cloudinary.models import CloudinaryField
# Create your models here.

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile') 
    name = models.CharField(max_length=40, blank=True, null=True)   
    bio = models.TextField(blank=True)
    institution = models.CharField(max_length=40, blank=True, null=True)
    affiliation = models.CharField(max_length=255, blank=True)
    profile_image = CloudinaryField('image', blank=True, null=True)
    date_joined = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"{self.institution or 'No Institution'} - {self.bio[:20]}"