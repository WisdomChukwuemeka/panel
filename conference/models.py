from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.text import slugify
from cloudinary_storage.storage import MediaCloudinaryStorage
from publications.models import Publication  # adjust path if needed
import uuid

User = get_user_model()

def generate_short_id():
    return uuid.uuid4().hex[:12]

class Conference(models.Model):
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True)

    description = models.TextField(blank=True)

    CONFERENCE_TYPES = [
        ("conference", "Academic Conference"),
        ("workshop", "Workshop"),
        ("symposium", "Symposium"),
        ("webinar", "Webinar"),
        ("summit", "Summit"),
        ("other", "Other"),
    ]
    type = models.CharField(max_length=20, choices=CONFERENCE_TYPES, default="conference")

    MODE_CHOICES = [
        ("online", "Online"),
        ("physical", "Physical"),
        ("hybrid", "Hybrid"),
    ]
    mode = models.CharField(max_length=20, choices=MODE_CHOICES, default="physical")

    STATUS_CHOICES = [
        ("upcoming", "Upcoming"),
        ("ongoing", "Ongoing"),
        ("past", "Past"),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="upcoming")

    start_date = models.DateTimeField()
    end_date = models.DateTimeField(blank=True, null=True)

    location = models.CharField(max_length=255, blank=True)
    website = models.URLField(blank=True)

    banner = models.ImageField(
        upload_to="conferences/banners/",
        blank=True,
        null=True,
        storage=MediaCloudinaryStorage()
    )

    organizer = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='organized_conferences'
    )

    publications = models.ManyToManyField(
        Publication,
        blank=True,
        related_name='conferences'
    )

    tags = models.CharField(
        max_length=255,
        blank=True,
        help_text="Comma-separated tags"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f"{self.name}-{generate_short_id()}")

        now = timezone.now()
        if self.start_date > now:
            self.status = "upcoming"
        elif self.end_date and self.end_date < now:
            self.status = "past"
        else:
            self.status = "ongoing"

        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
