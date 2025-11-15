from rest_framework import serializers
from .models import Publication, ReviewHistory, Category, Views, Notification
from payments.models import Subscription, Payment
import logging
from django.core.files.uploadedfile import InMemoryUploadedFile, TemporaryUploadedFile


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
    annotated_file = serializers.FileField(required=False, allow_null=True)
    
    class Meta:
        model = Publication
        fields = [
            "id",
            "doi", 
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
            'annotated_file', 
            'editor_comments',
        ]
        read_only_fields = [
            "author",
            "doi", 
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
                "draft": ['pending', 'under_review'],  # Updated: Skip pending for initial submissions if desired
                "pending": ["under_review"],
                "under_review": ["approved", "rejected"],
                "rejected": ['pending'],  # Updated: Direct to under_review on resubmission
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
    
    def validate(self, attrs):
        instance = self.instance
        status = attrs.get("status")

        # Only when author resubmits a rejected paper
        if (
            instance
            and instance.status == "rejected"
            and status in ["pending", "under_review"]
            and self.context["request"].user == instance.author
        ):

            changed = (
                attrs.get("title") != instance.title or
                attrs.get("abstract") != instance.abstract or
                attrs.get("content") != instance.content or
                "file" in self.context["request"].FILES or
                "video_file" in self.context["request"].FILES
            )
            if not changed:
                raise serializers.ValidationError({
                    "status": " Please ensure content is updated before resubmitting."
                })
        return attrs

    def update(self, instance, validated_data):
        logger.info(f"Updating publication with validated_data: {validated_data}")

        # Handle category updates
        category_name = validated_data.pop("category_name", None)

        # Check user permissions for status updates (assuming is_editor check)
        request = self.context.get('request')
        # Prevent non-editors from changing status
        # Instead of removing all status changes for non-editors:
        if request.user.role != "editor":
            if validated_data.get("status") not in ["pending", "under_review"]:
                validated_data.pop("status", None)


        if "status" in validated_data:
            new_status = validated_data["status"]
            if request.user.role != "editor":
                # Only allow rejected → pending transitions by author
                if instance.status == "rejected" and new_status == "pending":
                    instance.status = validated_data.pop("status")  # Set for authors
                else:
                    validated_data.pop("status", None)
            else:
                instance.status = validated_data.pop("status")

        # Editable fields for authors
        editable_fields = ["title", "abstract", "content", "file", "video_file", "keywords", "is_free_review", "rejection_note"]
        for field in editable_fields:
            if field in validated_data:
                value = validated_data.get(field)
                if field in ["file", "video_file"]:
                    value = validated_data.get(field)
                    if value in [None, "", "null", "undefined"]:
                        if getattr(instance, field):
                            getattr(instance, field).delete(save=False)
                        setattr(instance, field, None)
                    elif isinstance(value, (InMemoryUploadedFile, TemporaryUploadedFile)):
                        # Let Cloudinary handle it automatically
                        setattr(instance, field, value)
                else:
                    if value is not None:  # Skip None for non-file fields
                        setattr(instance, field, value)
                        

        # Handle category if provided
        if category_name is not None:
            category_obj, _ = Category.objects.get_or_create(name=category_name)
            instance.category = category_obj
            
        instance.editor_comments = validated_data.get('editor_comments', instance.editor_comments)
        if 'annotated_file' in validated_data:
            instance.annotated_file = validated_data['annotated_file']

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
        if len(value) > 2500:
            raise serializers.ValidationError("Abstract cannot exceed 2500 characters.")
        return value

    def validate_content(self, value):
        if not value.strip():
            raise serializers.ValidationError("Content cannot be empty or just whitespace.")
        if len(value) < 500:
            raise serializers.ValidationError("Content must be at least 500 characters long.")
        if len(value) > 15000:
            raise serializers.ValidationError("Content cannot exceed 15000 characters.")
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
    
    def annotated_file(self, obj):
        if obj.annotated_file:
            return obj.annotated_file.url
        return None
    

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
    
class StatsSerializer(serializers.Serializer):
    total_publications = serializers.IntegerField()
    approved = serializers.IntegerField()
    rejected = serializers.IntegerField()
    under_review = serializers.IntegerField()
    draft = serializers.IntegerField()
    total_likes = serializers.IntegerField()
    total_dislikes = serializers.IntegerField()
    monthly_data = serializers.ListField(child=serializers.DictField())
    editors_actions = serializers.ListField(child=serializers.DictField())
    total_payments = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_subscriptions = serializers.DecimalField(max_digits=12, decimal_places=2)
    payment_details = serializers.ListField(child=serializers.DictField())
    subscription_details = serializers.ListField(child=serializers.DictField())

    
# serializers.py (add this new serializer)
class ReviewHistorySerializer(serializers.ModelSerializer):
    publication_title = serializers.CharField(source='publication.title', read_only=True)
    author_name = serializers.CharField(source='publication.author.full_name', read_only=True)
    editor_name = serializers.CharField(source='editor.full_name', read_only=True)
    rejection_count = serializers.IntegerField(source='publication.rejection_count', read_only=True)

    class Meta:
        model = ReviewHistory
        fields = ['id', 'publication', 'publication_title', 'author_name', 'editor_name', 'action', 'note', 'timestamp', 'rejection_count']
        read_only_fields = fields
        
    