# tasks/models.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from publications.models import Notification  # Make sure this path is correct
from .models import Task
from django.utils import timezone
from accounts.models import User  # Adjust import based on your project structure


@receiver(post_save, sender=Task)
def notify_on_task_assignment(sender, instance, created, **kwargs):
    if created:
        Notification.objects.create(
            user=instance.assigned_to,
            type="task",
            related_task=instance,
            message=f"New Task Assigned: {instance.title}\n"
                    f"From: {instance.assigned_by.get_full_name() or 'Admin'}\n"
                    f"Due: {instance.due_date.strftime('%b %d, %Y') if instance.due_date else 'No due date'}",
        )

# Inside your Task model class
def mark_as_completed(self, reply_message: str, by_user: User = None) -> None:
    if self.status in ['completed', 'rejected']:
        raise ValueError("Task is already completed or rejected.")

    if by_user and by_user != self.assigned_to:
        raise PermissionError("Only the assigned editor can complete this task.")

    self.status = 'completed'
    self.reply_message = reply_message.strip()
    self.replied_at = timezone.now()
    self.save(update_fields=['status', 'reply_message', 'replied_at', 'updated_at'])

    # Notify the ADMIN who assigned the task
    Notification.objects.create(
        user=self.assigned_by,
        type="task",
        related_task=self,
        message=f"Task Completed by Editor\n\n"
                f"Editor: {self.assigned_to.get_full_name() or self.assigned_to.email}\n"
                f"Task: {self.title}\n"
                f"Due: {self.due_date.strftime('%b %d, %Y') if self.due_date else 'No due date'}\n\n"
                f"Reply:\n{reply_message.strip()}"
    )