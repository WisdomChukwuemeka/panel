from django.db import models
from accounts.models import User
from comments.models import Comment
from django.utils import timezone
import uuid

# Create your models here.
class CommentReaction(models.Model):
    EMOJI_CHOICES = [
    ("like", "Like"),
    ("love", "Love"),
    ("haha", "Haha"),
    ("wow", "Wow"),
    ("sad", "Sad"),
    ("angry", "Angry"),
    ("care", "Care"),
    ("confused", "Confused"),
    ("party", "Party"),
]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name="comment_reactions")
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    emoji = models.CharField(max_length=10, choices=EMOJI_CHOICES)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ("comment", "user")  # Prevents a user from reacting multiple times

    def __str__(self):
        return f"{self.user.get_full_name()} reacted {self.emoji} on comment {self.comment.id}"
