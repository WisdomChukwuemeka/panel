from django.db import models

# Create your models here.
from accounts.models import User

class Message(models.Model):
    full_name = models.CharField(max_length=25, blank=False, null=False)
    email = models.EmailField()
    text = models.TextField(max_length=500, blank=False, null=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.text