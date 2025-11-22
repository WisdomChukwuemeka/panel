from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import CommentReaction
from .serializers import AddReactionSerializer
from comments.models import Comment
from django.shortcuts import get_object_or_404

class AddOrUpdateReaction(APIView):
    
    def get_serializer_context(self):
        return {"request": self.request}
    
    def post(self, request):
        serializer = AddReactionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        comment_id = serializer.validated_data["comment_id"]
        emoji = serializer.validated_data["emoji"]
        user = request.user

        comment = get_object_or_404(Comment, id=comment_id)

        # Ensure dictionaries exist
        if comment.reactions is None:
            comment.reactions = {}
        if comment.user_reactions is None:
            comment.user_reactions = {}

        # Remove previous reaction count if exists
        previous_emoji = comment.user_reactions.get(str(user.id))
        if previous_emoji:
            if comment.reactions.get(previous_emoji, 0) > 0:
                comment.reactions[previous_emoji] -= 1

        # Add or update reaction
        CommentReaction.objects.update_or_create(
            comment=comment,
            user=user,
            defaults={"emoji": emoji}
        )

        # Update comment's reaction dict
        comment.reactions[emoji] = comment.reactions.get(emoji, 0) + 1
        comment.user_reactions[str(user.id)] = emoji
        comment.save()

        return Response({
            "reactions": comment.reactions,
            "user_reactions": comment.user_reactions
        }, status=status.HTTP_200_OK)
