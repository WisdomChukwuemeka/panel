from rest_framework import serializers
from .models import Publication, Category, Views, Notification
from payments.models import Subscription, Payment
import logging

logger = logging.getLogger(__name__)

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["name", "id"]

class ViewsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Views
        fields = ['id', 'publication', 'user', 'viewed', 'user_liked', 'user_disliked']
        read_only_fields = ['publication', 'user', 'viewed']

    def get_user(self, obj):
        return obj.user.full_name if obj.user else None

class PublicationSerializer(serializers.ModelSerializer):
    category_name = serializers.ChoiceField(choices=Category.CATEGORY_CHOICES, write_only=True)
    category_labels = serializers.SerializerMethodField(read_only=True)
    view_stats = ViewsSerializer(read_only=True)
    author = serializers.SerializerMethodField(read_only=True)
    status = serializers.CharField(required=False, read_only=False, default='draft')
    editor = serializers.SerializerMethodField(read_only=True)
    keywords = serializers.CharField(required=False, allow_blank=True)
    rejection_note = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    video_file = serializers.FileField(required=False, allow_null=True)
    is_free_review = serializers.BooleanField(default=False)  # Editable for resubmissions
    rejection_count = serializers.IntegerField(read_only=True)
    has_paid = serializers.SerializerMethodField()

    class Meta:
        model = Publication
        fields = [
            "id",
            "title",
            "abstract",
            "content",
            "file",
            "has_paid",
            "video_file",
            "author",
            "category_name",  # Input field
            "category_labels",  # Output field
            "keywords",
            "views",
            "view_stats",
            "is_free_review",
            "status",
            "editor",
            "publication_date",
            "created_at",
            "updated_at",
            "total_likes",
            "total_dislikes",
            "rejection_note",
            "rejection_count",
        ]
        read_only_fields = [
            "author",
            "views",
            "created_at",
            "updated_at",
            "view_stats",
            "has_paid",
            "category_labels",
            "id",
            "publication_date",
            "editor",
            "rejection_count",
        ]  # Removed 'is_free_review' to make it editable

    def validate_is_free_review(self, value):
        # Skip validation if not using a free review
        if not value:
            return value

        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("User authentication required.")

        subscription = Subscription.objects.filter(user=request.user).first()
        if not subscription:
            raise serializers.ValidationError("You don’t have any subscription.")

        if not subscription.has_free_review_available():
            raise serializers.ValidationError("No free reviews available.")

        return value

    def validate_status(self, value):
        instance = self.instance
        if instance:
            valid_transitions = {
                "draft": ["pending"],
                "pending": ["under_review"],
                "under_review": ["approved", "rejected"],
                "rejected": ["pending"],
                "approved": [],  # No transitions from approved
            }
            if value != instance.status and value not in valid_transitions.get(instance.status, []):
                raise serializers.ValidationError(f"Cannot transition from {instance.status} to {value}.")
        return value

    def get_total_likes(self, obj):
        return obj.total_likes()

    def get_total_dislikes(self, obj):
        return obj.total_dislikes()

    def create(self, validated_data):
        logger.info(f"Creating publication with validated_data: {validated_data}")
        category_name = validated_data.pop("category_name", None)
        publication = Publication.objects.create(**validated_data)
        if category_name:
            category_obj, _ = Category.objects.get_or_create(name=category_name)
            publication.category = category_obj
            publication.save()
        return publication

    def update(self, instance, validated_data):
        logger.info(f"Updating publication with validated_data: {validated_data}")

        # Handle category updates
        category_name = validated_data.pop("category_name", None)

        # Check user permissions for status updates (assuming is_editor check)
        request = self.context.get('request')
        # Prevent non-editors from changing status
        if request.user.role != "editor":
            validated_data.pop("status", None)

        if "status" in validated_data:
            if not request or not request.user.is_authenticated or request.user.role != 'editor':
                raise serializers.ValidationError("Only editors can update publication status.")
            instance.status = validated_data.pop("status")  # Remove status from validated_data

        # Editable fields for authors
        editable_fields = ["title", "abstract", "content", "file", "video_file", "keywords", "is_free_review", "rejection_note"]
        for field in editable_fields:
            if field in validated_data:
                value = validated_data.get(field)
                if field in ["file", "video_file"] and value in [None, "", "null", "undefined"]:
                    setattr(instance, field, None)
                elif value is not None:  # Skip None for non-file fields
                    setattr(instance, field, value)

        # Handle category if provided
        if category_name is not None:
            category_obj, _ = Category.objects.get_or_create(name=category_name)
            instance.category = category_obj

        instance.save()
        return instance

    def get_has_paid(self, obj):
        user = self.context['request'].user
        return Payment.objects.filter(
            user=user,
            payment_type='review_fee',
            metadata__publication_id=str(obj.id),
            status='success'
        ).exists()

    def get_category_labels(self, obj):
        return obj.category.get_name_display() if obj.category else None

    def get_author(self, obj):
        return obj.author.full_name

    def get_editor(self, obj):
        return obj.editor.full_name if obj.editor else None

    def validate_title(self, value):
        if not value.strip():
            raise serializers.ValidationError("Title cannot be empty or just whitespace.")
        if len(value) < 10:
            raise serializers.ValidationError("Title must be at least 10 characters long.")
        return value

    def validate_abstract(self, value):
        if not value.strip():
            raise serializers.ValidationError("Abstract cannot be empty or just whitespace.")
        if len(value) < 200:
            raise serializers.ValidationError("Abstract must be at least 200 characters long.")
        if len(value) > 1000:
            raise serializers.ValidationError("Abstract cannot exceed 1000 characters.")
        return value

    def validate_content(self, value):
        if not value.strip():
            raise serializers.ValidationError("Content cannot be empty or just whitespace.")
        if len(value) < 500:
            raise serializers.ValidationError("Content must be at least 500 characters long.")
        if len(value) > 10000:
            raise serializers.ValidationError("Content cannot exceed 10000 characters.")
        return value

    def validate_file(self, value):
        if value:
            if value.size > 10 * 1024 * 1024:  # 10MB limit
                raise serializers.ValidationError("File size cannot exceed 10MB.")
            if not value.name.lower().endswith(('.pdf', '.doc', '.docx')):
                raise serializers.ValidationError("Only PDF and Word documents are allowed.")
        return value

    def validate_video_file(self, value):
        if value:
            if value.size > 50 * 1024 * 1024:  # 50MB limit
                raise serializers.ValidationError("Video file size cannot exceed 50MB.")
            if not value.name.lower().endswith(('.mp4', '.avi', '.mov')):
                raise serializers.ValidationError("Only MP4, AVI, or MOV video files are allowed.")
        return value

    def validate_keywords(self, value):
        if value:
            if len(value) > 500:
                raise serializers.ValidationError("Keywords cannot exceed 500 characters.")
            keywords = [k.strip() for k in value.split(',') if k.strip()]
            if len(keywords) > 20:
                raise serializers.ValidationError("Cannot have more than 20 keywords.")
            return ','.join(keywords)
        return value

class NotificationSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField(read_only=True)
    related_publication = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Notification
        fields = ['id', 'user', 'message', 'is_read', 'created_at', 'related_publication']
        read_only_fields = ['created_at', 'related_publication']

    def get_user(self, obj):
        return obj.user.full_name

    def validate_message(self, value):
        if not value.strip():
            raise serializers.ValidationError("Message cannot be empty or just whitespace.")
        if len(value) > 1000:
            raise serializers.ValidationError("Message cannot exceed 1000 characters.")
        return value

    def update(self, instance, validated_data):
        instance.is_read = validated_data.get('is_read', instance.is_read)
        instance.save()
        return instance