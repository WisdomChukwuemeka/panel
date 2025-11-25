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
    
def generate_doi():
    # Simple example - you can later switch to CrossRef or a custom domain
    return f"10.1234/{uuid.uuid4().hex[:8]}"

def generate_short_id():
    return uuid.uuid4().hex[:12]

class Publication(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('under_review', 'Under Review'),
        ('rejected', 'Rejected'),
        ('approved', 'Approved'),
    ]

    id = models.CharField(
        primary_key=True,
        max_length=12,
        default=generate_short_id,
        editable=False,
    )
    
    doi = models.CharField(
    max_length=100,
    unique=True,
    blank=True,
    null=True,
    help_text="Digital Object Identifier for the publication",
    default=generate_doi
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
    annotated_file = models.FileField(
        upload_to='annotations/', 
        null=True, 
        blank=True, 
        storage=RawMediaCloudinaryStorage()
    )
    editor_comments = models.TextField(blank=True, null=True)

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
        is_new = self._state.adding  # True only when creating
        old_status = None

        # If updating, get the old instance to check for status changes
        if not is_new:
            old_instance = Publication.objects.get(pk=self.pk)
            old_status = old_instance.status

        # Force under_review when author resubmits a rejected paper
        if old_status == 'rejected' and self.status in ['draft', 'pending']:
            self.status = 'under_review'

        # Save the instance first (so we have pk and updated fields)
        super().save(*args, **kwargs)

        # # === NEW: Log editor actions to ReviewHistory ===
        # if old_status and old_status != self.status and self.editor:
        #     action_map = {
        #         'under_review': 'under_review',
        #         'approved': 'approved',
        #         'rejected': 'rejected'
        #     }
        #     action = action_map.get(self.status)
        #     if action:
        #         ReviewHistory.objects.create(
        #             publication=self,
        #             editor=self.editor,
        #             action=action,
        #             note=self.rejection_note if self.status == 'rejected' else self.editor_comments
        #         )


                    
    def total_likes(self):
        return self.view_stats.filter(user_liked=True).count()

    def total_dislikes(self):
        return self.view_stats.filter(user_disliked=True).count()

class ReviewHistory(models.Model):
    publication = models.ForeignKey(Publication, on_delete=models.CASCADE, related_name='review_history')
    editor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='review_actions')
    action = models.CharField(max_length=20, choices=[('under_review', 'Under Review'), ('approved', 'Approved'), ('rejected', 'Rejected')])
    note = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.editor} {self.action} {self.publication.title} at {self.timestamp}"
    

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