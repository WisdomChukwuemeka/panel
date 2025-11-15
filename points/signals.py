from django.db.models.signals import post_save
from django.dispatch import receiver
from comments.models import Comment
from .models import PointReward
from django.utils import timezone

@receiver(post_save, sender=Comment)
def award_points_on_comment(sender, instance, created, **kwargs):
    if created and instance.author != instance.publication.author:
        today = timezone.now().date()
        # One reward per day per commenter per publication
        if not PointReward.objects.filter(
            awarded_by=instance.author,
            publication=instance.publication,
            created_at__date=today
        ).exists():
            PointReward.objects.create(
                publication=instance.publication,
                comment=instance,
                awarded_by=instance.author,
                points=5
            )