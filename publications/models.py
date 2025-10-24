from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.conf import settings
from cloudinary_storage.storage import MediaCloudinaryStorage, VideoMediaCloudinaryStorage, RawMediaCloudinaryStorage
import uuid



User = get_user_model()

class Category(models.Model):
    CATEGORY_CHOICES = [
        ("journal", "Journal Article"),
        ("conference", "Conference Paper"),
        ("book", "Book/Book Chapter"),
        ("thesis", "Thesis/Dissertation"),
        ("report", "Technical Report"),
        ("review", "Review Paper"),
        ("case_study", "Case Study"),
        ("editorial", "Editorial/Opinion"),
        ("news", "News/Blog"),
        ("other", "Other"),
    ]

    name = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES,
        unique=True,
        primary_key=True,  # Explicitly set as primary key
    )

    class Meta:
        indexes = [
            models.Index(fields=['name']),
        ]
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.get_name_display()

def generate_short_id():
    return uuid.uuid4().hex[:12]

class Publication(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('under_review', 'Under Review'),
        ('rejected', 'Rejected'),
        ('needs_revision', 'Needs Revision'),
        ('approved', 'Approved'),
    ]

    id = models.CharField(
        primary_key=True,
        max_length=12,
        default=generate_short_id,
        editable=False,
    )
    title = models.CharField(max_length=255)
    abstract = models.TextField()
    content = models.TextField(blank=True)
    is_free_review = models.BooleanField(default=False)  # Added field
    file = models.FileField(upload_to='publications/', blank=True, storage=RawMediaCloudinaryStorage())
    video_file = models.FileField(upload_to='videos/', blank=True, storage=VideoMediaCloudinaryStorage())
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='publications'
    )
    category = models.ForeignKey(Category, on_delete=models.CASCADE, null=True,  blank=True)
    keywords = models.TextField(blank=True, help_text="Comma-separated list of keywords (e.g., machine learning, AI)")
    views = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft'
    )
    editor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='edited_publications'
    )
    rejection_count = models.PositiveIntegerField(default=0)
    rejection_note = models.TextField(blank=True, null=True)
    publication_date = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['author', 'publication_date']),
            models.Index(fields=['title', 'abstract', 'keywords'], name='search_idx'),
            models.Index(fields=['status']),
        ]
        ordering = ['-publication_date']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        is_new = self._state.adding  # this is True only when creating
        old_status = None

        # If updating, get the old instance to check for status changes
        if not is_new:
            old_instance = Publication.objects.get(pk=self.pk)
            old_status = old_instance.status

        # Save the instance first to ensure pk is set
        super().save(*args, **kwargs)

        if is_new:
            # Notify editors for new submission
            editors = User.objects.filter(role='editor')
            if editors.exists():
                for editor in editors:
                    Notification.objects.create(
                        user=editor,
                        message=f"New publication '{self.title}' submitted for review by {self.author.full_name} at {timezone.now().strftime('%I:%M %p WAT, %B %d, %Y')}.",
                        related_publication=self
                    )
            else:
                # Notify author if no editors are available
                Notification.objects.create(
                    user=self.author,
                    message=f"No editors available to review your publication '{self.title}' submitted at {timezone.now().strftime('%I:%M %p WAT, %B %d, %Y')}. Please contact an administrator.",
                    related_publication=self
                )
        elif old_status != self.status:
            # Notify author of status change
            Notification.objects.create(
                user=self.author,
                message=f"Your publication '{self.title}' status changed to '{self.get_status_display()}' at {timezone.now().strftime('%I:%M %p WAT, %B %d, %Y')}.",
                related_publication=self
            )
            # Notify editors of status change (if not already approved)
            if self.status != 'approved':
                editors = User.objects.filter(role='editor')
                for editor in editors:
                    Notification.objects.create(
                        user=editor,
                        message=f"Publication '{self.title}' status updated to '{self.get_status_display()}' at {timezone.now().strftime('%I:%M %p WAT, %B %d, %Y')}.",
                        related_publication=self
                    )
                    
    def total_likes(self):
        return self.view_stats.filter(user_liked=True).count()

    def total_dislikes(self):
        return self.view_stats.filter(user_disliked=True).count()


class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    related_publication = models.ForeignKey(
        Publication,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications'
    )
    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification for {self.user.full_name}: {self.message}"

class Views(models.Model):
    publication = models.ForeignKey('Publication', on_delete=models.CASCADE, related_name='view_stats')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    user_liked = models.BooleanField(default=False)
    user_disliked = models.BooleanField(default=False)
    viewed = models.BooleanField(default=False)  # Add this field
    
    class Meta:
        unique_together = ('publication', 'user')

    def __str__(self):
        return f"{self.user} - {self.publication.title}"