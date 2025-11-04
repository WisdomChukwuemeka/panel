from django.db import models
from django.utils import timezone
from comments.models import Comment
from publications.models import Publication
from accounts.models import User
import uuid
class PointReward(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    publication = models.ForeignKey(Publication, on_delete=models.CASCADE, related_name="point_rewards")
    comment = models.ForeignKey(Comment, null=True, blank=True, on_delete=models.SET_NULL, related_name="point_rewards")
    awarded_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="awarded_point_rewards")
    points = models.IntegerField(default=5)
    created_at = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"{self.points} points awarded to {self.publication.title[:30]}"