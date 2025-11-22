from rest_framework import serializers
from .models import CommentReaction

class CommentReactionSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(read_only=True)
    comment = serializers.UUIDField()
    user = serializers.UUIDField()
    emoji = serializers.ChoiceField(choices=CommentReaction.EMOJI_CHOICES)
    created_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = CommentReaction
        fields = ["id", "comment", "user", "emoji", "created_at"]

class AddReactionSerializer(serializers.Serializer):
    comment_id = serializers.UUIDField()
    emoji = serializers.ChoiceField(choices=CommentReaction.EMOJI_CHOICES)
