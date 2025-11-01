# comments/serializers.py
from rest_framework import serializers
from .models import Comment
from accounts.models import User  # For user details if needed

class CommentSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Comment
        fields = ["id", "publication", "author", "author_name", "text", "created_at"]
        read_only_fields = ["id", "author", "publication", "created_at"]

    def get_author_name(self, obj):
        return obj.author.get_full_name() or obj.author.email

