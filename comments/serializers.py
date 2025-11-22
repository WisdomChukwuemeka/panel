# comments/serializers.py
from rest_framework import serializers
from .models import Comment
from accounts.models import User

class CommentSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()
    is_current_user = serializers.SerializerMethodField()
    reactions = serializers.JSONField(required=False)
    audio_url = serializers.SerializerMethodField()
    user_reaction = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            "id", "text", "audio", "audio_url",
            "author_name", "is_current_user",
            "created_at", "reactions", "user_reaction",
        ]

    def get_author_name(self, obj):
        return obj.author.get_full_name() or obj.author.email

    def get_is_current_user(self, obj):
        request = self.context.get("request")
        return request and request.user.is_authenticated and obj.author == request.user

    def get_audio_url(self, obj):
        request = self.context.get("request")
        if obj.audio:
            return request.build_absolute_uri(obj.audio.url)
        return None


    def get_user_reaction(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None

        user_id = str(request.user.id)

        # FIX: user_reactions stored inside reactions?
        if hasattr(obj, "user_reactions") and obj.user_reactions:
            return obj.user_reactions.get(user_id)

        # fallback: user reaction stored inside reactions?
        return obj.reactions.get("user", {}).get(user_id)
