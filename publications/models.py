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
    cover_image = models.ImageField(
        upload_to='covers/%Y/%m/',
        storage=RawMediaCloudinaryStorage(),
        blank=True,
        null=True,
        help_text="Featured image (16:9 recommended)"
    )
    co_author_names = models.JSONField(default=list, blank=True)  # Stores list of strings, e.g., ["John Doe", "Jane Smith"]
    # license = models.CharField(
    #     max_length=50,
    #     choices=[
    #         ('cc-by', 'CC BY 4.0'),
    #         ('cc-by-sa', 'CC BY-SA 4.0'),
    #         ('cc-by-nc', 'CC BY-NC 4.0'),
    #     ],
    #     default='cc-by'
    # )
    publication_date = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    volume = models.CharField(max_length=50, blank=True, null=True)



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
    TYPE_CHOICES = (
        ("task", "Task"),
        ("publication", "Publication"),
        ("message", "Message"),
        ("comment", "Comment"),
    )
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
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    message = models.TextField()
    related_task = models.ForeignKey(
        "tasks.Task",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="notifications"
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
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        unique_together = ('publication', 'user')

    def __str__(self):
        return f"{self.user} - {self.publication.title}"   
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
#     # models.py (2025 Production Edition)

# from django.db import models
# from django.contrib.auth import get_user_model
# from django.utils import timezone
# from django.core.exceptions import ValidationError
# from django.core.validators import MinLengthValidator, FileExtensionValidator
# from cloudinary_storage.storage import RawMediaCloudinaryStorage, VideoMediaCloudinaryStorage
# import uuid
# from taggit.managers import TaggableManager  # pip install django-taggit
# from django.urls import reverse
# from django.utils.text import slugify

# User = get_user_model()


# def generate_short_id():
#     return uuid.uuid4().hex[:12]


# def generate_doi():
#     """Replace later with CrossRef/DataCite integration"""
#     return f"10.56726/journivor.{uuid.uuid4().hex[:10]}"


# class Category(models.Model):
#     name = models.CharField(max_length=50, unique=True, primary_key=True)
#     slug = models.SlugField(max_length=60, unique=True, blank=True)
#     description = models.CharField(max_length=255, blank=True)
#     icon = models.CharField(max_length=50, blank=True, help_text="Bootstrap/Iconify icon name")
#     is_active = models.BooleanField(default=True)

#     class Meta:
#         verbose_name_plural = "Categories"
#         ordering = ['name']

#     def save(self, *args, **kwargs):
#         if not self.slug:
#             self.slug = slugify(self.name)
#         super().save(*args, **kwargs)

#     def __str__(self):
#         return self.get_name_display()


# class Publication(models.Model):
#     STATUS_CHOICES = [
#         ('draft', 'Draft'),
#         ('pending', 'Pending Review'),
#         ('under_review', 'Under Review'),
#         ('revision_required', 'Revision Required'),
#         ('rejected', 'Rejected'),
#         ('approved', 'Approved'),
#         ('published', 'Published'),  # Final state after fee paid
#     ]

#     id = models.CharField(primary_key=True, default=generate_short_id, max_length=12, editable=False)
#     doi = models.CharField(max_length=100, unique=True, blank=True, null=True, default=generate_doi)
#     slug = models.SlugField(max_length=280, unique=True, blank=True)

#     title = models.CharField(
#         max_length=280,
#         validators=[MinLengthValidator(15)],
#         help_text="Clear, descriptive title (15+ chars)"
#     )
#     subtitle = models.CharField(max_length=280, blank=True)
#     abstract = models.TextField(validators=[MinLengthValidator(150), MinLengthValidator(150)])
#     content = models.TextField(blank=True)  # For HTML-rich content or rendered markdown

#     # Files
#     manuscript = models.FileField(
#         upload_to='manuscripts/%Y/%m/',
#         storage=RawMediaCloudinaryStorage(),
#         validators=[FileExtensionValidator(['pdf', 'docx', 'doc'])],
#         help_text="Main article file (PDF preferred)"
#     )
#     supplementary_file = models.FileField(
#         upload_to='supplementary/%Y/%m/',
#         storage=RawMediaCloudinaryStorage(),
#         blank=True,
#         null=True
#     )
#     cover_image = models.ImageField(
#         upload_to='covers/%Y/%m/',
#         storage=RawMediaCloudinaryStorage(),
#         blank=True,
#         null=True,
#         help_text="Featured image (16:9 recommended)"
#     )
#     video_abstract = models.FileField(
#         upload_to='videos/%Y/%m/',
#         storage=VideoMediaCloudinaryStorage(),
#         blank=True,
#         null=True,
#         validators=[FileExtensionValidator(['mp4', 'mov', 'avi'])]
#     )

#     # Relationships
#     author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='publications')
#     co_authors = models.ManyToManyField(User, related_name='co_authored_papers', blank=True)
#     category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
#     editor = models.ForeignKey(
#         User,
#         on_delete=models.SET_NULL,
#         null=True,
#         blank=True,
#         related_name='assigned_papers'
#     )

#     # Keywords (modern way)
#     tags = TaggableManager(blank=True, help_text="Comma-separated tags (e.g., AI, Medicine, Climate)")

#     # Status & Review
#     status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', db_index=True)
#     is_free_review = models.BooleanField(default=False)
#     rejection_count = models.PositiveSmallIntegerField(default=0)
#     rejection_note = models.TextField(blank=True)
#     editor_comments = models.TextField(blank=True)
#     annotated_manuscript = models.FileField(
#         upload_to='annotated/%Y/%m/',
#         storage=RawMediaCloudinaryStorage(),
#         blank=True,
#         null=True
#     )

#     # Metrics
#     views_count = models.PositiveBigIntegerField(default=0)
#     downloads_count = models.PositiveBigIntegerField(default=0)
#     citation_count = models.PositiveIntegerField(default=0)

#     # Dates
#     submitted_at = models.DateTimeField(null=True, blank=True)
#     published_at = models.DateTimeField(null=True, blank=True)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     # Flags
#     is_featured = models.BooleanField(default=False, help_text="Show on homepage?")
#     is_open_access = models.BooleanField(default=True)
#     license = models.CharField(
#         max_length=50,
#         choices=[
#             ('cc-by', 'CC BY 4.0'),
#             ('cc-by-sa', 'CC BY-SA 4.0'),
#             ('cc-by-nc', 'CC BY-NC 4.0'),
#         ],
#         default='cc-by'
#     )

#     class Meta:
#         indexes = [
#             models.Index(fields=['status']),
#             models.Index(fields=['author']),
#             models.Index(fields=['created_at']),
#             models.Index(fields=['published_at']),
#             models.Index(fields=['-views_count']),
#             models.Index(fields=['-downloads_count']),
#             models.Index(fields=['doi']),
#             models.Index(fields=['slug']),
#         ]
#         ordering = ['-created_at']
#         permissions = [
#             ("can_publish_immediately", "Can bypass review process"),
#             ("can_assign_editor", "Can assign editors"),
#             ("can_view_all_submissions", "Can view all submissions"),
#         ]

#     def __str__(self):
#         return f"{self.title} — {self.author.get_full_name()}"

#     def save(self, *args, **kwargs):
#         # Auto-slug
#         if not self.slug:
#             base_slug = slugify(self.title)
#             slug = base_slug
#             counter = 1
#             while Publication.objects.filter(slug=slug).exists():
#                 slug = f"{base_slug}-{counter}"
#                 counter += 1
#             self.slug = slug

#         # Set submitted_at on first submission
#         if self.status in ['pending', 'under_review'] and not self.submitted_at:
#             self.submitted_at = timezone.now()

#         # Set published_at
#         if self.status == 'published' and not self.published_at:
#             self.published_at = timezone.now()

#         super().save(*args, **kwargs)

#     def get_absolute_url(self):
#         return reverse('publication-detail', kwargs={'slug': self.slug})

#     # Properties
#     @property
#     def is_published(self):
#         return self.status == 'published'

#     @property
#     def days_under_review(self):
#         if self.submitted_at:
#             return (timezone.now() - self.submitted_at).days
#         return 0

#     def clean(self):
#         if self.status == 'published' and not self.manuscript:
#             raise ValidationError("Published articles must have a manuscript file.")

#     def total_likes(self):
#         return self.view_stats.filter(user_liked=True).count()

#     def total_downloads(self):
#         # You can track downloads separately or increment on file access
#         return self.downloads_count


# class ReviewHistory(models.Model):
#     publication = models.ForeignKey(Publication, on_delete=models.CASCADE, related_name='review_history')
#     editor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='review_actions')
#     action = models.CharField(max_length=30)
#     note = models.TextField(blank=True)
#     timestamp = models.DateTimeField(auto_now_add=True)
#     is_visible_to_author = models.BooleanField(default=True)

#     class Meta:
#         ordering = ['-timestamp']

#     def __str__(self):
#         return f"{self.action} by {self.editor} on {self.publication.title}"


# class Notification(models.Model):
#     NOTIFICATION_TYPES = [
#         ('publication', 'Publication Update'),
#         ('task', 'Editor Task'),
#         ('review', 'Review Action'),
#         ('payment', 'Payment'),
#         ('system', 'System'),
#     ]

#     user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
#     type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default='system', db_index=True)
#     title = models.CharField(max_length=150)
#     message = models.TextField()
#     is_read = models.BooleanField(default=False, db_index=True)
#     related_publication = models.ForeignKey(Publication, null=True, blank=True, on_delete=models.CASCADE)
#     related_task = models.ForeignKey('tasks.Task', null=True, blank=True, on_delete=models.SET_NULL)
#     created_at = models.DateTimeField(auto_now_add=True, db_index=True)

#     class Meta:
#         ordering = ['-created_at']
#         indexes = [
#             models.Index(fields=['user', '-created_at']),
#             models.Index(fields=['is_read']),
#             models.Index(fields=['type']),
#         ]

#     def __str__(self):
#         return f"{self.title} → {self.user}"


# class Views(models.Model):
#     publication = models.ForeignKey(Publication, on_delete=models.CASCADE, related_name='view_stats')
#     user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
#     session_key = models.CharField(max_length=40, null=True, blank=True)  # For anonymous
#     ip_address = models.GenericIPAddressField(null=True, blank=True)
#     user_agent = models.TextField(blank=True)
#     liked = models.BooleanField(default=False)
#     disliked = models.BooleanField(default=False)
#     viewed_at = models.DateTimeField(auto_now_add=True)

#     class Meta:
#         unique_together = ('publication', 'session_key')
#         indexes = [
#             models.Index(fields=['publication', '-viewed_at']),
#         ]