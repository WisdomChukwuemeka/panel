# comments/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Comment
from publications.models import Notification

@receiver(post_save, sender=Comment)
def notify_publication_author(sender, instance, created, **kwargs):
    if created:
        publication = instance.publication
        author = publication.author

        # Avoid notifying the comment author themselves
        if instance.author != author:
            Notification.objects.create(
                user=author,
                message=f"{instance.author.get_full_name() or instance.author.email} commented on your publication '{publication.title}'.",
                related_publication=publication
            )
