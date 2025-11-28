from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Publication, Notification, User

@receiver(post_save, sender=Publication)
def handle_publication_notifications(sender, instance, created, **kwargs):
    """
    Signal handler to create notifications for new publications and status changes.
    This replaces the notification logic previously in Publication.save().
    """
    publication = instance
    old_status = None

    if not created:
        # For updates, we need to compare with previous status.
        # Signals don't provide old instance directly, so we can use a pre_save signal if needed,
        # but for simplicity, assume we fetch it (though this might not be atomic).
        # Better approach: Use a pre_save to store old_status in a thread-local or instance attr.
        # But for now, we'll mimic the original logic by checking if status changed.
        # Note: This assumes status is only changed via save, and we compare post-save.
        pass  # We'll handle created separately, and for updates, rely on kwargs or custom logic.

    if created:
        # Notify editors for new submission
        editors = User.objects.filter(role='editor')
        if editors.exists():
            for editor in editors:
                Notification.objects.create(
                    user=editor,
                    message=f"New publication '{publication.title}' submitted for review by {publication.author.full_name} at {timezone.now().strftime('%I:%M %p WAT, %B %d, %Y')}.",
                    related_publication=publication
                )
        else:
            Notification.objects.create(
                user=publication.author,
                message=f"No editors available to review your publication '{publication.title}' submitted at {timezone.now().strftime('%I:%M %p WAT, %B %d, %Y')}. Please contact an administrator.",
                related_publication=publication
            )
    else:
        # For updates: We need to check if status changed.
        # Since post_save doesn't have old_instance, we can add a custom instance attr in pre_save.
        # For this example, assume we have a way to detect status change (or move full logic here).
        # To make it work properly, we'll add a pre_save signal below to store old_status.
        if hasattr(publication, '_old_status') and publication._old_status != publication.status:
            old_status = publication._old_status
            # Notify author
            Notification.objects.create(
                user=publication.author,
                message=f"Your publication '{publication.title}' status changed to '{publication.get_status_display()}' at {timezone.now().strftime('%I:%M %p WAT, %B %d, %Y')}.",
                related_publication=publication
            )
            # Notify editors
            editors = User.objects.filter(role='editor')
            for editor in editors:
                Notification.objects.create(
                    user=editor,
                    message=f"Publication '{publication.title}' status updated to '{publication.get_status_display()}' at {timezone.now().strftime('%I:%M %p WAT, %B %d, %Y')}.",
                    related_publication=publication
                )


from django.db.models.signals import pre_save

@receiver(pre_save, sender=Publication)
def store_old_status(sender, instance, **kwargs):
    """
    Pre-save signal to store the old status for comparison in post_save.
    """
    if instance.pk:
        try:
            old_instance = sender.objects.get(pk=instance.pk)
            instance._old_status = old_instance.status
        except sender.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None

# If you have Conference in a separate app, you can add similar signals for it.
# For example, in conferences/signals.py:

# from django.db.models.signals import post_save
# from django.dispatch import receiver
# from publications.models import Notification, User  # Cross-app import
# from .models import Conference

# @receiver(post_save, sender=Conference)
# def handle_conference_notifications(sender, instance, created, **kwargs):
#     if created:
#         editors = User.objects.filter(role='editor')
#         for editor in editors:
#             Notification.objects.create(
#                 user=editor,
#                 message=f"New conference '{instance.title}' added by {instance.organizer.full_name if instance.organizer else 'Anonymous'} at {timezone.now().strftime('%I:%M %p WAT, %B %d, %Y')}.",
#             )