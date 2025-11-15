# rewardcodes/models.py
from django.db import models
from django.utils import timezone
from accounts.models import User
from publications.models import Publication
from comments.models import Comment
from points.models import PointReward  # Assuming the app name is 'pointrewards'
from django.db.models import Sum
import uuid
from datetime import timedelta

class RewardQualification(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="reward_qualification")
    last_qualified_at = models.DateTimeField(null=True, blank=True)

class RewardCode(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reward_codes")
    code = models.UUIDField(default=uuid.uuid4)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    redeemed = models.BooleanField(default=False)
    redeemed_publication = models.ForeignKey(Publication, null=True, blank=True, on_delete=models.SET_NULL)

    def save(self, *args, **kwargs):
        if not self.pk:
            self.expires_at = self.created_at + timedelta(weeks=2)
        super().save(*args, **kwargs)

    def __str__(self):
        return str(self.code)