# tasks/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from publications.models import Notification
from .models import Task

@receiver(post_save, sender=Task)
def notify_on_task_assignment(sender, instance, created, **kwargs):
    if created:
        Notification.objects.create(
            user=instance.assigned_to,
            message=f"New Task Assigned\n\n"
                    f"From: {instance.assigned_by.get_full_name() or 'Admin'}\n"
                    f"Title: {instance.title}\n"
                    f"Description: {instance.description}\n"
                    f"Due Date: {instance.due_date.strftime('%b %d, %Y') if instance.due_date else 'Not set'}",
        )