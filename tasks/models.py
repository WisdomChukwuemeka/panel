# tasks/models.py
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from publications.models import Notification
from accounts.models import User

User = get_user_model()


class Task(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
    )

    title = models.CharField(max_length=255)
    description = models.TextField()

    # ForeignKeys with helpful related_names
    assigned_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='tasks_assigned_by_me',
        help_text="Admin who created the task"
    )
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='tasks_assigned_to_me',
        limit_choices_to={'role': 'editor'},
        help_text="Editor assigned to this task"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True  # Speeds up filtering by status
    )

    reply_message = models.TextField(blank=True, null=True)
    replied_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    due_date = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Task'
        verbose_name_plural = 'Tasks'
        permissions = [
            ("can_assign_task", "Can assign tasks to editors"),
            ("can_reply_task", "Can reply to assigned tasks"),
        ]
        # Ensures one user doesn't get duplicate active tasks with same title
        constraints = [
            models.UniqueConstraint(
                fields=['title', 'assigned_to'],
                condition=models.Q(status__in=['pending', 'in_progress']),
                name='unique_active_task_per_editor'
            )
        ]

    def __str__(self):
        return f"{self.title} → {self.assigned_to.get_full_name() or self.assigned_to.email}"

    # ————————————————————
    # Clean & Safe Methods
    # ————————————————————
    def mark_as_completed(self, reply_message: str, by_user: User = None) -> None:
        """
        Marks task as completed and sends notification to assigner.
        Only callable by the assigned editor.
        """
        if self.status in ['completed', 'rejected']:
            raise ValueError("Task is already completed or rejected.")

        if by_user and by_user != self.assigned_to:
            raise PermissionError("Only the assigned editor can complete this task.")

        self.status = 'completed'
        self.reply_message = reply_message.strip()
        self.replied_at = timezone.now()
        self.save(update_fields=['status', 'reply_message', 'replied_at', 'updated_at'])

        # Notify the admin who assigned it
        Notification.objects.create(
            user=self.assigned_by,
            message=(
                f"Task Completed\n\n"
                f"Editor: {self.assigned_to.get_full_name() or self.assigned_to.email}\n"
                f"Task: {self.title}\n"
                f"Due: {self.due_date.strftime('%b %d, %Y') if self.due_date else 'No due date'}\n\n"
                f"Reply:\n{reply_message.strip()}"
            ),
            # Optional: add a link to the task in admin
        )

    def mark_as_in_progress(self, by_user: User = None) -> None:
        """Allows editor to mark task as in progress"""
        if self.status != 'pending':
            raise ValueError("Can only start pending tasks.")

        if by_user and by_user != self.assigned_to:
            raise PermissionError("Only the assigned editor can update this task.")

        self.status = 'in_progress'
        self.save(update_fields=['status', 'updated_at'])

    # ————————————————————
    # Helpful Properties
    # ————————————————————
    @property
    def is_overdue(self) -> bool:
        if not self.due_date:
            return False
        return timezone.now() > self.due_date and self.status not in ['completed', 'rejected']

    @property
    def status_badge_color(self) -> str:
        return {
            'pending': 'yellow',
            'in_progress': 'blue',
            'completed': 'green',
            'rejected': 'red',
        }.get(self.status, 'gray')