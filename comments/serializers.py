# comments/serializers.py
from rest_framework import serializers
from .models import Comment
from accounts.models import User  # For user details if needed

# comments/serializers.py
class CommentSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()
    is_current_user = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ["id", "text", "author_name", "is_current_user", "created_at"]

    def get_author_name(self, obj):
        return obj.author.get_full_name() or obj.author.email

    def get_is_current_user(self, obj):
        request = self.context.get("request")
        return request and request.user.is_authenticated and obj.author == request.user